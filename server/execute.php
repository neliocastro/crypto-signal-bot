<?php
/**
 * execute.php - BRACO da execucao (lado servidor, IP FIXO na whitelist Gate.io).
 *
 * Recebe a "intencao de ordem" assinada (HMAC) vinda do executor.py.
 * FASE 1 = DRY-RUN: valida, simula slippage lendo o book real e LOGA.
 * NUNCA envia ordem real enquanto $DRY_RUN = true.
 *
 * Seguranca (cinto duplo):
 *   1) HMAC: so aceita corpo assinado com o segredo compartilhado.
 *   2) IP fixo: a Gate.io so aceita ordens deste servidor (whitelist).
 *   3) Teto rigido: recusa notional acima de MAX_NOTIONAL_USDT.
 *   4) Idempotencia: mesmo signal_id nunca executa 2x.
 *
 * Chaves Gate.io: FORA da web root (ex.: /home/ineocom/cryptosignals/secrets/.env). Nunca aqui.
 */

// ===================== CONFIG =====================
$DRY_RUN            = true;                 // FASE 1: true. So mude p/ false na Fase 2.
$MAX_NOTIONAL_USDT  = 5.0;                 // teto rigido (protege de bug no Python)
$SYMBOL_WHITELIST   = ['HYPE/USDT','LINK/USDT','BTC/USDT','ETH/USDT','SOL/USDT',
                       'XRP/USDT','TRX/USDT','BNB/USDT','AAVE/USDT'];
$LOG_FILE           = __DIR__ . '/execution_log.jsonl';
$SEEN_FILE          = __DIR__ . '/seen_signals.json';   // idempotencia

// Segredos fora da web root:
$secrets = @parse_ini_file('/home/ineocom/cryptosignals/secrets/.env');
$HMAC_SECRET = $secrets['EXECUTION_HMAC_SECRET'] ?? '';
$GATE_KEY    = $secrets['GATE_API_KEY'] ?? '';
$GATE_SECRET = $secrets['GATE_API_SECRET'] ?? '';

// ===================== HELPERS =====================
function respond($arr, $code = 200) {
    http_response_code($code);
    header('Content-Type: application/json');
    echo json_encode($arr);
    exit;
}
function log_event($file, $record) {
    $record['ts'] = gmdate('c');
    file_put_contents($file, json_encode($record, JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND);
}

// ----- Assinatura Gate.io v4 (DIFERENTE do HMAC Python<->PHP) -----
// SIGN = HMAC-SHA512 de: "METHOD\nPATH\nQUERY\nSHA512(body)\nTIMESTAMP"
function gate_headers($method, $path, $query, $body, $key, $secret) {
    $ts = time();
    $hashed_body = hash('sha512', $body);
    $payload = "$method\n$path\n$query\n$hashed_body\n$ts";
    $sign = hash_hmac('sha512', $payload, $secret);
    return [
        "KEY: $key",
        "Timestamp: $ts",
        "SIGN: $sign",
        "Content-Type: application/json",
        "Accept: application/json",
    ];
}

// ===================== 1) VALIDA HMAC =====================
$raw = file_get_contents('php://input');
$sig = $_SERVER['HTTP_X_SIGNATURE'] ?? '';
$calc = hash_hmac('sha256', $raw, $HMAC_SECRET);
if (!$HMAC_SECRET || !hash_equals($calc, $sig)) {
    respond(['status' => 'rejected', 'reason' => 'assinatura invalida'], 401);
}
$order = json_decode($raw, true);
if (!$order) respond(['status' => 'rejected', 'reason' => 'payload invalido'], 400);

// ===================== 2) SANITY-CHECKS =====================
$symbol   = $order['symbol'] ?? '';
$notional = (float)($order['notional_usdt'] ?? 0);
$sid      = $order['signal_id'] ?? '';

if (!in_array($symbol, $SYMBOL_WHITELIST, true))
    respond(['status' => 'rejected', 'reason' => 'symbol fora da whitelist']);
if ($notional <= 0 || $notional > $MAX_NOTIONAL_USDT)
    respond(['status' => 'rejected', 'reason' => "notional fora do teto ($MAX_NOTIONAL_USDT)"]);

// idempotencia
$seen = file_exists($SEEN_FILE) ? json_decode(file_get_contents($SEEN_FILE), true) : [];
if (isset($seen[$sid]))
    respond(['status' => 'duplicate', 'reason' => 'signal_id ja processado', 'signal_id' => $sid]);

// ===================== 3) PRECO REAL (book) p/ slippage =====================
// GET publico no ticker da Gate.io (nao executa nada). Simula o ask atual.
$pair = str_replace('/', '_', $symbol);   // BTC/USDT -> BTC_USDT
$ticker_url = "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=$pair";
$ask = null;
$resp = @file_get_contents($ticker_url);
if ($resp && ($t = json_decode($resp, true)) && isset($t[0]['lowest_ask'])) {
    $ask = (float)$t[0]['lowest_ask'];
}
$ref = (float)($order['ref_price'] ?? 0);
$slippage_pct = ($ask && $ref) ? round((($ask - $ref) / $ref) * 100, 4) : null;

// ===================== 4) DRY-RUN vs REAL =====================
if ($DRY_RUN) {
    $result = [
        'status'        => 'dry_run',
        'symbol'        => $symbol,
        'notional_usdt' => $notional,
        'ref_price'     => $ref,
        'sim_fill_price'=> $ask,            // preenchimento simulado = ask atual
        'slippage_pct'  => $slippage_pct,
        'note'          => 'FASE 1: ordem NAO enviada (dry-run)',
    ];
} else {
    // ===================== FASE 2: EXECUCAO REAL (Gate.io v4) =====================
    // Triplo cinto continua valendo: HMAC + whitelist + teto $MAX_NOTIONAL_USDT.
    // Ordem a MERCADO de compra. Na Gate.io spot market-buy, "amount" = USDT a gastar.
    if (!$GATE_KEY || !$GATE_SECRET) {
        $result = ['status' => 'error', 'reason' => 'chave Gate.io ausente no .env do servidor'];
    } else {
        $path  = '/api/v4/spot/orders';
        $bodyArr = [
            'currency_pair' => $pair,            // ex.: BTC_USDT
            'side'          => 'buy',
            'type'          => 'market',
            'account'       => 'spot',
            'amount'        => (string)$notional, // market-buy: amount em USDT (quote)
            'text'          => 't-' . substr($sid, 0, 12), // tag p/ rastrear (idempotencia)
        ];
        $bodyJson = json_encode($bodyArr, JSON_UNESCAPED_SLASHES);
        $headers  = gate_headers('POST', $path, '', $bodyJson, $GATE_KEY, $GATE_SECRET);

        $ch = curl_init('https://api.gateio.ws' . $path);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $bodyJson,
            CURLOPT_HTTPHEADER     => $headers,
            CURLOPT_TIMEOUT        => 15,
        ]);
        $raw_resp = curl_exec($ch);
        $http     = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_err = curl_error($ch);
        curl_close($ch);

        $gate = $raw_resp ? json_decode($raw_resp, true) : null;
        if ($curl_err) {
            $result = ['status' => 'error', 'reason' => "curl: $curl_err"];
        } elseif ($http >= 200 && $http < 300 && isset($gate['id'])) {
            $result = [
                'status'       => 'filled',
                'order_id'     => $gate['id'],
                'symbol'       => $symbol,
                'side'         => 'buy',
                'gate_status'  => $gate['status']        ?? null,
                'filled_total' => $gate['filled_total']  ?? null,  // USDT gasto
                'fill_price'   => $gate['avg_deal_price'] ?? $ask,  // preco medio real
                'amount_base'  => $gate['amount']        ?? null,
                'http'         => $http,
            ];
        } else {
            // Gate.io rejeitou (saldo, par, permissao...). Loga o motivo, nao quebra.
            $result = [
                'status' => 'rejected_by_exchange',
                'http'   => $http,
                'reason' => $gate['label'] ?? ($gate['message'] ?? 'erro desconhecido'),
                'detail' => $gate,
            ];
        }
    }
}

// ===================== 5) LOG + idempotencia + resposta =====================
log_event($LOG_FILE, ['event' => 'execute', 'order' => $order, 'result' => $result]);
$seen[$sid] = gmdate('c');
file_put_contents($SEEN_FILE, json_encode($seen));
respond($result);
