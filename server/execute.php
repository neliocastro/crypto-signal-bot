<?php
/**
 * execute.php - BRACO da execucao (lado servidor, IP FIXO na whitelist Gate.io).
 *
 * Recebe a "intencao de ordem" assinada (HMAC) vinda do executor.py.
 * Fase 2 ATIVA: executa ordem real de compra a mercado e cria TP/SL
 * nativos (price_orders) na Gate.io logo apos o fill.
 *
 * Seguranca (cinto):
 *   1) HMAC: so aceita corpo assinado com o segredo compartilhado.
 *   2) IP fixo: a Gate.io so aceita ordens deste servidor (whitelist).
 *   3) Teto rigido: recusa notional acima de MAX_NOTIONAL_USDT.
 *   4) Idempotencia: mesmo signal_id nunca executa 2x.
 *
 * Chaves Gate.io: FORA da web root (/home/ineocom/cryptosignals/secrets/.env).
 */

// ===================== CONFIG =====================
$DRY_RUN            = false;                // FASE 2 ativa (ordens reais)
$TPSL_ENABLED       = true;                 // kill-switch do TP/SL nativo (false = compra sem gatilho)
$MAX_NOTIONAL_USDT  = 5.0;                  // teto rigido (protege de bug no Python)
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

// ----- Assinatura Gate.io v4 -----
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

// POST autenticado generico na Gate.io v4. Retorna [http, json, err].
function gate_post($path, $bodyArr, $key, $secret) {
    $bodyJson = json_encode($bodyArr, JSON_UNESCAPED_SLASHES);
    $headers  = gate_headers('POST', $path, '', $bodyJson, $key, $secret);
    $ch = curl_init('https://api.gateio.ws' . $path);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $bodyJson,
        CURLOPT_HTTPHEADER     => $headers,
        CURLOPT_TIMEOUT        => 15,
    ]);
    $raw  = curl_exec($ch);
    $http = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);
    return [$http, ($raw ? json_decode($raw, true) : null), $err];
}

// Busca regras do par (cacheado por request). Casas da base, casas do preco, min base.
function pair_rules($pair) {
    static $cache = [];
    if (isset($cache[$pair])) return $cache[$pair];
    $url = "https://api.gateio.ws/api/v4/spot/currency_pairs/$pair";
    $resp = @file_get_contents($url);
    $d = $resp ? json_decode($resp, true) : null;
    $rules = [
        'amount_precision' => isset($d['amount_precision']) ? (int)$d['amount_precision'] : 6,
        'price_precision'  => isset($d['precision'])        ? (int)$d['precision']        : 6,
        'min_base_amount'  => isset($d['min_base_amount'])  ? (float)$d['min_base_amount'] : 0.0,
    ];
    $cache[$pair] = $rules;
    return $rules;
}

// Trunca (floor) um valor para N casas decimais e devolve string limpa.
function fmt_floor($value, $decimals) {
    $factor = pow(10, $decimals);
    $truncated = floor($value * $factor) / $factor;
    $s = number_format($truncated, $decimals, '.', '');
    // remove zeros a direita e ponto solto (Gate aceita ambos, mas fica limpo)
    if (strpos($s, '.') !== false) $s = rtrim(rtrim($s, '0'), '.');
    return $s === '' ? '0' : $s;
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
        'sim_fill_price'=> $ask,
        'slippage_pct'  => $slippage_pct,
        'note'          => 'DRY-RUN: ordem NAO enviada',
    ];
} else {
    // ===================== FASE 2: EXECUCAO REAL (Gate.io v4) =====================
    if (!$GATE_KEY || !$GATE_SECRET) {
        $result = ['status' => 'error', 'reason' => 'chave Gate.io ausente no .env do servidor'];
    } else {
        // ----- 4.1) COMPRA a mercado (amount = USDT a gastar; market spot exige ioc) -----
        $path = '/api/v4/spot/orders';
        $bodyArr = [
            'currency_pair' => $pair,
            'side'          => 'buy',
            'type'          => 'market',
            'account'       => 'spot',
            'amount'        => (string)$notional,
            'time_in_force' => 'ioc',                       // market spot exige ioc (nunca gtc)
            'text'          => 't-' . substr($sid, 0, 12),
        ];
        list($http, $gate, $curl_err) = gate_post($path, $bodyArr, $GATE_KEY, $GATE_SECRET);

        if ($curl_err) {
            $result = ['status' => 'error', 'reason' => "curl: $curl_err"];
        } elseif ($http >= 200 && $http < 300 && isset($gate['id'])) {
            $fill_price = (float)($gate['avg_deal_price'] ?? $ask);
            $result = [
                'status'       => 'filled',
                'order_id'     => $gate['id'],
                'symbol'       => $symbol,
                'side'         => 'buy',
                'gate_status'  => $gate['status']        ?? null,
                'filled_total' => $gate['filled_total']  ?? null,  // USDT gasto
                'fill_price'   => $fill_price,                     // preco medio real
                'amount_base'  => $gate['amount']        ?? null,
                'http'         => $http,
            ];

            // ----- 4.2) TP/SL NATIVOS (price_orders) -----
            $tpsl = ['enabled' => $TPSL_ENABLED, 'tp' => null, 'sl' => null, 'note' => null];

            if ($TPSL_ENABLED) {
                $sl_price = isset($order['sl_price']) ? (float)$order['sl_price'] : 0.0;
                $tp_price = isset($order['tp_price']) ? (float)$order['tp_price'] : 0.0;

                $rules = pair_rules($pair);
                $apz = $rules['amount_precision'];   // casas da BASE
                $ppz = $rules['price_precision'];     // casas do PRECO
                $minb = $rules['min_base_amount'];

                // quantidade BASE comprada: usa amount real do fill se vier; senao filled_total/fill_price
                $base_raw = 0.0;
                if (isset($gate['amount']) && (float)$gate['amount'] > 0) {
                    $base_raw = (float)$gate['amount'];
                } elseif ($fill_price > 0) {
                    $base_raw = (float)($result['filled_total']) / $fill_price;
                }
                // margem p/ fee: vende 99.8% da base (fee 0.2% sai na base em market-buy) -> evita "saldo insuficiente"
                $base_sellable = $base_raw * 0.998;
                $base_qty_s = fmt_floor($base_sellable, $apz);
                $base_qty_f = (float)$base_qty_s;

                if ($base_qty_f <= 0) {
                    $tpsl['note'] = 'base_qty calculada = 0; TP/SL NAO criados';
                } elseif ($minb > 0 && $base_qty_f < $minb) {
                    $tpsl['note'] = "base_qty ($base_qty_f) abaixo do min_base_amount ($minb); TP/SL NAO criados";
                } else {
                    $ppath = '/api/v4/spot/price_orders';

                    // TAKE-PROFIT: vende quando preco SOBE ate tp_price
                    if ($tp_price > 0) {
                        $tp_s = fmt_floor($tp_price, $ppz);
                        $tpBody = [
                            'trigger' => ['price' => $tp_s, 'rule' => '>=', 'expiration' => 86400],
                            'put'     => ['type' => 'market', 'side' => 'sell',
                                          'amount' => $base_qty_s, 'account' => 'spot',
                                          'time_in_force' => 'ioc'],
                            'market'  => $pair,
                        ];
                        list($h2, $g2, $e2) = gate_post($ppath, $tpBody, $GATE_KEY, $GATE_SECRET);
                        $tpsl['tp'] = ['http'=>$h2, 'id'=>($g2['id']??null),
                                       'err'=>($e2 ?: ($g2['label']??null)), 'price'=>$tp_s];
                    }

                    // STOP-LOSS: vende quando preco CAI ate sl_price
                    if ($sl_price > 0) {
                        $sl_s = fmt_floor($sl_price, $ppz);
                        $slBody = [
                            'trigger' => ['price' => $sl_s, 'rule' => '<=', 'expiration' => 86400],
                            'put'     => ['type' => 'market', 'side' => 'sell',
                                          'amount' => $base_qty_s, 'account' => 'spot',
                                          'time_in_force' => 'ioc'],
                            'market'  => $pair,
                        ];
                        list($h3, $g3, $e3) = gate_post($ppath, $slBody, $GATE_KEY, $GATE_SECRET);
                        $tpsl['sl'] = ['http'=>$h3, 'id'=>($g3['id']??null),
                                       'err'=>($e3 ?: ($g3['label']??null)), 'price'=>$sl_s];
                    }
                    $tpsl['base_qty'] = $base_qty_s;
                }
            } else {
                $tpsl['note'] = 'TPSL_ENABLED=false';
            }
            $result['tpsl'] = $tpsl;

        } else {
            // Gate.io rejeitou (saldo, par, permissao...). Loga, nao quebra.
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
