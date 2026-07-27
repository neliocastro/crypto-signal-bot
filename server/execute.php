<?php
/**
 * execute.php - BRACO da execucao (lado servidor, IP FIXO na whitelist Gate.io).
 * FIX 1..5 (compra + TP/SL) + FIX 6 (acao update_trailing: cria->confirma->DELETE antigo).
 * FIX 7 (2026-07-10): base_qty do TP/SL derivada do fill REAL (filled_total/fill_price).
 *   Antes usava $gate['amount'], que em MARKET BUY vem em QUOTE (USDT), nao em base:
 *   gatilhos eram criados p/ vender ~4.99 ETH em vez de ~0.0029 -> disparavam,
 *   a venda falhava por saldo insuficiente e o gatilho morria (TP/SL fantasma).
 */
$DRY_RUN            = false;
$TPSL_ENABLED       = true;
$REQUIRE_PROTECTION = true;
$MAX_NOTIONAL_USDT  = 5.0;   // alinhado ao Python (EXECUTION_MAX_NOTIONAL_USDT)
$SYMBOL_WHITELIST   = ['PAXG/USDT','HYPE/USDT','LINK/USDT','BTC/USDT','ETH/USDT','SOL/USDT','XRP/USDT','TRX/USDT','BNB/USDT','AAVE/USDT'];
$LOG_FILE           = __DIR__ . '/execution_log.jsonl';
$SEEN_FILE          = __DIR__ . '/seen_signals.json';
$SAFE_PRICE_PREC = ['BTC_USDT'=>1,'ETH_USDT'=>2,'SOL_USDT'=>2,'XRP_USDT'=>4,'TRX_USDT'=>4,'BNB_USDT'=>1,'LINK_USDT'=>3,'HYPE_USDT'=>2,'AAVE_USDT'=>2]; // conferido via /spot/currency_pairs 2026-07-26
$SAFE_AMOUNT_PREC = ['BTC_USDT'=>6,'ETH_USDT'=>4,'SOL_USDT'=>3,'XRP_USDT'=>1,'TRX_USDT'=>1,'BNB_USDT'=>3,'LINK_USDT'=>2,'HYPE_USDT'=>3,'AAVE_USDT'=>3]; // conferido via /spot/currency_pairs 2026-07-26
$SAFE_MIN_BASE = ['BTC_USDT'=>0.000001,'ETH_USDT'=>0.001,'SOL_USDT'=>0.001,'XRP_USDT'=>0.1,'TRX_USDT'=>0.01,'BNB_USDT'=>0.001,'LINK_USDT'=>0.01,'HYPE_USDT'=>0.01,'AAVE_USDT'=>0.001];
$secrets = @parse_ini_file('/home/ineocom/cryptosignals/secrets/.env');
$HMAC_SECRET = $secrets['EXECUTION_HMAC_SECRET'] ?? '';
$GATE_KEY    = $secrets['GATE_API_KEY'] ?? '';
$GATE_SECRET = $secrets['GATE_API_SECRET'] ?? '';
function respond($arr, $code = 200) { http_response_code($code); header('Content-Type: application/json'); echo json_encode($arr); exit; }
function log_event($file, $record) { $record['ts'] = gmdate('c'); file_put_contents($file, json_encode($record, JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND); }
function http_get_json($url, $retries = 1) {
    for ($i = 0; $i <= $retries; $i++) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_TIMEOUT=>8, CURLOPT_CONNECTTIMEOUT=>5, CURLOPT_HTTPHEADER=>['User-Agent: crypto-signal-bot/1.0','Accept: application/json']]);
        $resp = curl_exec($ch); $http = curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
        if ($resp !== false && $resp !== '' && $http >= 200 && $http < 300) { $d = json_decode($resp, true); if (is_array($d)) return $d; }
        if ($i < $retries) usleep(300000);
    }
    return null;
}
function gate_headers($method, $path, $query, $body, $key, $secret) {
    $ts = time(); $payload = "$method\n$path\n$query\n" . hash('sha512', $body) . "\n$ts";
    return ["KEY: $key","Timestamp: $ts","SIGN: ".hash_hmac('sha512',$payload,$secret),"Content-Type: application/json","Accept: application/json"];
}
function gate_post($path, $bodyArr, $key, $secret) {
    $bodyJson = json_encode($bodyArr, JSON_UNESCAPED_SLASHES); $ch = curl_init('https://api.gateio.ws' . $path);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_POST=>true, CURLOPT_POSTFIELDS=>$bodyJson, CURLOPT_HTTPHEADER=>gate_headers('POST',$path,'',$bodyJson,$key,$secret), CURLOPT_TIMEOUT=>15]);
    $raw = curl_exec($ch); $http = curl_getinfo($ch, CURLINFO_HTTP_CODE); $err = curl_error($ch); curl_close($ch);
    return [$http, ($raw ? json_decode($raw, true) : null), $err];
}
function gate_delete($path, $key, $secret) {
    $ch = curl_init('https://api.gateio.ws' . $path);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_CUSTOMREQUEST=>'DELETE', CURLOPT_HTTPHEADER=>gate_headers('DELETE',$path,'','',$key,$secret), CURLOPT_TIMEOUT=>15]);
    $raw = curl_exec($ch); $http = curl_getinfo($ch, CURLINFO_HTTP_CODE); $err = curl_error($ch); curl_close($ch);
    return [$http, ($raw ? json_decode($raw, true) : null), $err];
}
function pair_rules($pair) {
    global $SAFE_PRICE_PREC, $SAFE_AMOUNT_PREC, $SAFE_MIN_BASE; static $cache = [];
    if (isset($cache[$pair])) return $cache[$pair];
    $d = http_get_json("https://api.gateio.ws/api/v4/spot/currency_pairs/$pair", 1);
    $fb_price = $SAFE_PRICE_PREC[$pair] ?? null; $fb_amount = $SAFE_AMOUNT_PREC[$pair] ?? null; $fb_minb = $SAFE_MIN_BASE[$pair] ?? 0.0;
    $apz_api = isset($d['amount_precision']) ? (int)$d['amount_precision'] : null;
    $ppz_api = isset($d['precision']) ? (int)$d['precision'] : null;
    $minb_api = isset($d['min_base_amount']) ? (float)$d['min_base_amount'] : null;
    $source = 'api';
    if ($ppz_api === null || $apz_api === null) $source = ($fb_price !== null) ? 'fallback_table' : 'fallback_blind';
    $rules = ['amount_precision'=>$apz_api ?? ($fb_amount ?? 6), 'price_precision'=>$ppz_api ?? ($fb_price ?? 6), 'min_base_amount'=>$minb_api ?? $fb_minb, 'source'=>$source];
    $cache[$pair] = $rules; return $rules;
}
function fmt_floor($value, $decimals) {
    $f = pow(10, $decimals); $s = number_format(floor($value * $f) / $f, $decimals, '.', '');
    if (strpos($s, '.') !== false) $s = rtrim(rtrim($s, '0'), '.'); return $s === '' ? '0' : $s;
}
function decimal_places($numStr) {
    $numStr = (string)$numStr; $pos = strpos($numStr, '.'); if ($pos === false) return 0;
    return strlen(rtrim(substr($numStr, $pos + 1), '0'));
}
$raw = file_get_contents('php://input');
$sig = $_SERVER['HTTP_X_SIGNATURE'] ?? '';
$calc = hash_hmac('sha256', $raw, $HMAC_SECRET);
if (!$HMAC_SECRET || !hash_equals($calc, $sig)) respond(['status'=>'rejected','reason'=>'assinatura invalida'], 401);
$order = json_decode($raw, true);
if (!$order) respond(['status'=>'rejected','reason'=>'payload invalido'], 400);
$action = $order['action'] ?? '';
if ($action === 'update_trailing') {
    $symbol = $order['symbol'] ?? '';
    if (!in_array($symbol, $SYMBOL_WHITELIST, true)) respond(['status'=>'rejected','reason'=>'symbol fora da whitelist']);
    $new_sl_price = (float)($order['new_sl_price'] ?? 0); $base_qty = (string)($order['base_qty'] ?? '');
    $old_id = $order['old_sl_order_id'] ?? ''; $tsid = $order['signal_id'] ?? '';
    if ($new_sl_price <= 0 || $base_qty === '' || (float)$base_qty <= 0) respond(['status'=>'error','reason'=>'update_trailing: new_sl_price/base_qty invalidos','signal_id'=>$tsid]);
    if (!$GATE_KEY || !$GATE_SECRET) respond(['status'=>'error','reason'=>'chave Gate.io ausente no .env']);
    $pair = str_replace('/', '_', $symbol); $rules = pair_rules($pair); $ppz = $rules['price_precision'];
    $sl_s = fmt_floor($new_sl_price, $ppz);
    if (decimal_places($sl_s) > $ppz || (float)$sl_s <= 0) {
        $rej = ['status'=>'error','reason'=>"precisao new_sl ($sl_s) excede ppz ($ppz)",'symbol'=>$symbol,'signal_id'=>$tsid,'rules_source'=>$rules['source']];
        log_event($LOG_FILE, ['event'=>'update_trailing','order'=>$order,'result'=>$rej]); respond($rej);
    }
    $ppath = '/api/v4/spot/price_orders';
    $slBody = ['trigger'=>['price'=>$sl_s,'rule'=>'<=','expiration'=>2592000],'put'=>['type'=>'market','side'=>'sell','amount'=>$base_qty,'account'=>'normal','time_in_force'=>'ioc'],'market'=>$pair];
    list($hc, $gc, $ec) = gate_post($ppath, $slBody, $GATE_KEY, $GATE_SECRET); $new_id = $gc['id'] ?? null;
    if (!($hc >= 200 && $hc < 300 && $new_id)) {
        $rej = ['status'=>'error','reason'=>'falha ao criar novo stop; antigo MANTIDO','symbol'=>$symbol,'signal_id'=>$tsid,'http'=>$hc,'detail'=>($ec ?: ($gc['label'] ?? $gc['message'] ?? null))];
        log_event($LOG_FILE, ['event'=>'update_trailing','order'=>$order,'result'=>$rej]); respond($rej);
    }
    $del = null;
    if ($old_id !== '') { list($hd, $gd, $ed) = gate_delete($ppath.'/'.rawurlencode((string)$old_id), $GATE_KEY, $GATE_SECRET); $del = ['http'=>$hd,'err'=>($ed ?: ($gd['label'] ?? null))]; }
    $ok = ['status'=>'trailing_updated','symbol'=>$symbol,'signal_id'=>$tsid,'new_sl'=>['id'=>$new_id,'price'=>$sl_s,'http'=>$hc],'old_sl'=>['id'=>$old_id,'delete'=>$del],'rules_source'=>$rules['source']];
    log_event($LOG_FILE, ['event'=>'update_trailing','order'=>$order,'result'=>$ok]); respond($ok);
}
$symbol = $order['symbol'] ?? ''; $notional = (float)($order['notional_usdt'] ?? 0); $sid = $order['signal_id'] ?? '';
if (!in_array($symbol, $SYMBOL_WHITELIST, true)) respond(['status'=>'rejected','reason'=>'symbol fora da whitelist']);
if ($notional <= 0 || $notional > $MAX_NOTIONAL_USDT) respond(['status'=>'rejected','reason'=>"notional fora do teto ($MAX_NOTIONAL_USDT)"]);
$sl_price_in = isset($order['sl_price']) ? (float)$order['sl_price'] : 0.0; $tp_price_in = isset($order['tp_price']) ? (float)$order['tp_price'] : 0.0;
if ($REQUIRE_PROTECTION && $TPSL_ENABLED && $sl_price_in <= 0 && $tp_price_in <= 0) {
    $rej = ['status'=>'rejected','reason'=>'ssem TP nem SL (ATR=0?) - compra recusada (posicao nua)','symbol'=>$symbol,'signal_id'=>$sid];
    log_event($LOG_FILE, ['event'=>'execute','order'=>$order,'result'=>$rej]);
    $seen = file_exists($SEEN_FILE) ? json_decode(file_get_contents($SEEN_FILE), true) : []; $seen[$sid] = gmdate('c'); file_put_contents($SEEN_FILE, json_encode($seen)); respond($rej);
}
$seen = file_exists($SEEN_FILE) ? json_decode(file_get_contents($SEEN_FILE), true) : [];
if (isset($seen[$sid])) respond(['status'=>'duplicate','reason'=>'signal_id ja processado','signal_id'=>$sid]);
$pair = str_replace('/', '_', $symbol); $ask = null;
$t = http_get_json("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=$pair", 1);
if ($t && isset($t[0]['lowest_ask'])) $ask = (float)$t[0]['lowest_ask'];
$ref = (float)($order['ref_price'] ?? 0); $slippage_pct = ($ask && $ref) ? round((($ask - $ref) / $ref) * 100, 4) : null;
if ($DRY_RUN) {
    $result = ['status'=>'dry_run','symbol'=>$symbol,'notional_usdt'=>$notional,'ref_price'=>$ref,'sim_fill_price'=>$ask,'slippage_pct'=>$slippage_pct];
} else {
    if (!$GATE_KEY || !$GATE_SECRET) { $result = ['status'=>'error','reason'=>'chave Gate.io ausente no .env']; }
    else {
        $bodyArr = ['currency_pair'=>$pair,'side'=>'buy','type'=>'market','account'=>'sspot','amount'=>(string)$notional,'time_in_force'=>'ioc','text'=>'t-'.substr($sid,0,10)];
        list($http, $gate, $curl_err) = gate_post('/api/v4/spot/orders', $bodyArr, $GATE_KEY, $GATE_SECRET);
        if ($curl_err) { $result = ['status'=>'error','reason'=>"curl: $curl_err"]; }
        elseif ($http >= 200 && $http < 300 && isset($gate['id'])) {
            $fill_price = (float)($gate['avg_deal_price'] ?? $ask);
            $result = ['status'=>'filled','order_id'=>$gate['id'],'symbol'=>$symbol,'side'=>'buy','gate_status'=>$gate['status']??null,'filled_total'=>$gate['filled_total']??null,'fill_price'=>$fill_price,'amount_base'=>$gate['amount']??null,'http'=>$http];
            $tpsl = ['enabled'=>$TPSL_ENABLED,'tp'=>null,'sl'=>null,'note'=>null];
            if ($TPSL_ENABLED) {
                $sl_price = $sl_price_in; $tp_price = $tp_price_in; $rules = pair_rules($pair);
                $apz = $rules['amount_precision']; $ppz = $rules['price_precision']; $minb = $rules['min_base_amount']; $tpsl['rules_source'] = $rules['source'];
                // FIX 7: em MARKET BUY, $gate['amount'] esta em QUOTE (USDT) - JAMAIS usar como base.
                // Base REAL comprada = filled_total (USDT preenchidos) / preco medio do fill.
                $base_raw = 0.0;
                if ($fill_price > 0 && isset($gate['filled_total']) && (float)$gate['filled_total'] > 0) {
                    $base_raw = (float)$gate['filled_total'] / $fill_price;
                }
                // Cinto extra (fail-safe > fail-silent): base*fill jamais excede o notional (+5%).
                if ($fill_price > 0 && ($base_raw * $fill_price) > ($notional * 1.05)) {
                    $tpsl['note'] = "sanity: base_raw ($base_raw) x fill ($fill_price) excede notional ($notional); TP/SL NAO criados";
                    $base_raw = 0.0;
                }
                $base_qty_s = fmt_floor($base_raw * 0.998, $apz); $base_qty_f = (float)$base_qty_s;
                if ($base_qty_f <= 0) { if (empty($tpsl['note'])) $tpsl['note'] = 'base_qty = 0; TP/SL NAO criados'; }
                elseif ($minb > 0 && $base_qty_f < $minb) { $tpsl['note'] = "base_qty ($base_qty_f) < min_base ($minb); TP/SL NAO criados"; }
                else {
                    $ppath = '/api/v4/spot/price_orders';
                    if ($tp_price > 0) {
                        $tp_s = fmt_floor($tp_price, $ppz);
                        if (decimal_places($tp_s) > $ppz) { $tpsl['tp'] = ['skipped'=>true,'reason'=>"precisao TP ($tp_s) excede ppz ($ppz)"]; }
                        else {
                            $tpBody = ['trigger'=>['price'=>$tp_s,'rule'=>'>=','expiration'=>2592000],'put'=>['type'=>'market','side'=>'sell','amount'=>$base_qty_s,'account'=>'normal','time_in_force'=>'ioc'],'market'=>$pair];
                            list($h2,$g2,$e2) = gate_post($ppath, $tpBody, $GATE_KEY, $GATE_SECRET);
                            $tpsl['tp'] = ['http'=>$h2,'id'=>($g2['id']??null),'err'=>($e2?:($g2['label']??null)),'price'=>$tp_s];
                        }
                    }
                    if ($sl_price > 0) {
                        $sl_s = fmt_floor($sl_price, $ppz);
                        if (decimal_places($sl_s) > $ppz) { $tpsl['sl'] = ['skipped'=>true,'reason'=>"precisao SL ($sl_s) excede ppz ($ppz)"]; }
                        else {
                            $slBody = ['trigger'=>['price'=>$sl_s,'rule'=>'<=','expiration'=>2592000],'put'=>['type'=>'market','side'=>'sell','amount'=>$base_qty_s,'account'=>'normal','time_in_force'=>'ioc'],'market'=>$pair];
                            list($h3,$g3,$e3) = gate_post($ppath, $slBody, $GATE_KEY, $GATE_SECRET);
                            $tpsl['sl'] = ['http'=>$h3,'id'=>($g3['id']??null),'err'=>($e3?:($g3['label']??null)),'price'=>$sl_s];
                        }
                    }
                    $tpsl['base_qty'] = $base_qty_s;
                }
            } else { $tpsl['note'] = 'TPSL_ENABLED=false'; }
            $result['tpsl'] = $tpsl;
        } else { $result = ['status'=>'rejected_by_exchange','http'=>$http,'reason'=>$gate['label']??($gate['message']??'erro desconhecido'),'detail'=>$gate]; }
    }
}
log_event($LOG_FILE, ['event'=>'execute','order'=>$order,'result'=>$result]);
$seen[$sid] = gmdate('c'); file_put_contents($SEEN_FILE, json_encode($seen)); respond($result);
