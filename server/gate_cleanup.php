#!/usr/bin/env php
<?php
/**
 * gate_cleanup.php — Reconciliação e limpeza de price-triggered orders órfãs (Gate.io spot)
 *
 * CONTEXTO: a Gate.io NÃO tem OCO nativo no spot. TP e SL são condicionais independentes.
 * Quando o SL dispara e vende a base, o TP fica órfão (status=open apontando para base
 * já vendida) e vai morrer em BALANCE_NOT_ENOUGH. Este script encontra e cancela esses órfãos.
 *
 * USO (via SSH, jailshell — rodar de ~/, nunca de /tmp):
 *   php ~/gate_cleanup.php list             -> lista TODAS as condicionais abertas + saldos (read-only)
 *   php ~/gate_cleanup.php orphans          -> DRY-RUN: mostra quais SELLs estão órfãs (read-only)
 *   php ~/gate_cleanup.php cancel-orphans   -> cancela as órfãs detectadas (grava log)
 *   php ~/gate_cleanup.php cancel ID [ID..] -> cancela ids específicos (grava log)
 *
 * REGRA DE OURO: rode 'orphans' e confira ANTES de rodar 'cancel-orphans'.
 * Log de auditoria: ~/gate_cleanup_log.jsonl
 */

$ENV_PATH = '/home/ineocom/cryptosignals/secrets/.env';
$API_BASE = 'https://api.gateio.ws';
$PREFIX   = '/api/v4';
$LOG_FILE = getenv('HOME') . '/gate_cleanup_log.jsonl';

$env = @parse_ini_file($ENV_PATH);
if (!$env || empty($env['GATE_API_KEY']) || empty($env['GATE_API_SECRET'])) {
    fwrite(STDERR, "ERRO: nao consegui ler GATE_API_KEY/GATE_API_SECRET em $ENV_PATH\n");
    exit(1);
}
$GLOBALS['KEY']    = $env['GATE_API_KEY'];
$GLOBALS['SECRET'] = $env['GATE_API_SECRET'];

function gate_request($method, $path, $query = '', $body = '') {
    global $API_BASE, $PREFIX;
    $ts = (string) time();
    $bodyHash = hash('sha512', $body);
    $signStr = $method . "\n" . $PREFIX . $path . "\n" . $query . "\n" . $bodyHash . "\n" . $ts;
    $sign = hash_hmac('sha512', $signStr, $GLOBALS['SECRET']);
    $url = $API_BASE . $PREFIX . $path . ($query !== '' ? ('?' . $query) : '');
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST  => $method,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 25,
        CURLOPT_USERAGENT      => 'crypto-signal-bot-cleanup/1.0',
        CURLOPT_HTTPHEADER     => [
            'Accept: application/json',
            'Content-Type: application/json',
            'KEY: ' . $GLOBALS['KEY'],
            'Timestamp: ' . $ts,
            'SIGN: ' . $sign,
        ],
    ]);
    if ($body !== '') { curl_setopt($ch, CURLOPT_POSTFIELDS, $body); }
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);
    if ($resp === false) { return [0, null, 'curl_error: ' . $err]; }
    return [$code, json_decode($resp, true), $resp];
}

function audit_log($entry) {
    global $LOG_FILE;
    $entry['ts_utc'] = gmdate('c');
    @file_put_contents($LOG_FILE, json_encode($entry) . "\n", FILE_APPEND);
}

function get_open_price_orders() {
    list($code, $data, $raw) = gate_request('GET', '/spot/price_orders', 'status=open');
    if ($code !== 200 || !is_array($data)) {
        fwrite(STDERR, "ERRO listando price_orders (HTTP $code): $raw\n");
        exit(1);
    }
    return $data;
}

function get_balances() {
    list($code, $data, $raw) = gate_request('GET', '/spot/accounts');
    if ($code !== 200 || !is_array($data)) {
        fwrite(STDERR, "ERRO listando saldos (HTTP $code): $raw\n");
        exit(1);
    }
    $bal = [];
    foreach ($data as $a) {
        $bal[$a['currency']] = (float) $a['available'] + (float) $a['locked'];
    }
    return $bal;
}

function fmt_order($o) {
    $t = isset($o['trigger']) ? $o['trigger'] : [];
    $p = isset($o['put']) ? $o['put'] : [];
    return sprintf(
        "  id=%s  %s  %s %s  amount=%s  trigger %s %s  ctime=%s",
        $o['id'],
        str_pad($o['market'], 10),
        strtoupper(isset($p['side']) ? $p['side'] : '?'),
        isset($p['type']) ? $p['type'] : '?',
        isset($p['amount']) ? $p['amount'] : '?',
        isset($t['rule']) ? $t['rule'] : '?',
        isset($t['price']) ? $t['price'] : '?',
        isset($o['ctime']) ? gmdate('Y-m-d H:i', (int)$o['ctime']) . ' UTC' : '?'
    );
}

function find_orphans($orders, $balances) {
    $orphans = [];
    foreach ($orders as $o) {
        $p = isset($o['put']) ? $o['put'] : [];
        if (!isset($p['side']) || strtolower($p['side']) !== 'sell') { continue; }
        $base = explode('_', $o['market'])[0];
        $have = isset($balances[$base]) ? $balances[$base] : 0.0;
        $need = (float) (isset($p['amount']) ? $p['amount'] : 0);
        // margem de 1% para poeira/arredondamento
        if ($have < $need * 0.99) {
            $o['_base'] = $base; $o['_have'] = $have; $o['_need'] = $need;
            $orphans[] = $o;
        }
    }
    return $orphans;
}

function cancel_order($id) {
    list($code, $data, $raw) = gate_request('DELETE', '/spot/price_orders/' . $id);
    $ok = ($code === 200);
    printf("  %s cancelamento id=%s (HTTP %d)%s\n", $ok ? 'OK' : 'FALHOU', $id, $code, $ok ? '' : ' -> ' . $raw);
    audit_log(['action' => 'cancel', 'order_id' => (string)$id, 'http' => $code, 'response' => $data]);
    return $ok;
}

// ---------------- main ----------------
$cmd = isset($argv[1]) ? $argv[1] : 'list';

switch ($cmd) {
    case 'list':
        $orders = get_open_price_orders();
        $bal = get_balances();
        echo "== Price-triggered orders ABERTAS (" . count($orders) . ") ==\n";
        foreach ($orders as $o) { echo fmt_order($o) . "\n"; }
        echo "\n== Saldos spot (nao-zero) ==\n";
        foreach ($bal as $cur => $v) {
            if ($v > 0) { printf("  %-6s %s\n", $cur, rtrim(rtrim(sprintf('%.8f', $v), '0'), '.')); }
        }
        break;

    case 'orphans':
        $orders = get_open_price_orders();
        $bal = get_balances();
        $orphans = find_orphans($orders, $bal);
        echo "== DRY-RUN: SELLs orfas (saldo de base insuficiente) ==\n";
        if (!$orphans) { echo "  nenhuma orfa detectada.\n"; break; }
        foreach ($orphans as $o) {
            echo fmt_order($o) . "\n";
            printf("    -> precisa %.8f %s, tem %.8f (ORFA)\n", $o['_need'], $o['_base'], $o['_have']);
        }
        echo "\nConfira acima. Para cancelar: php ~/gate_cleanup.php cancel-orphans\n";
        break;

    case 'cancel-orphans':
        $orders = get_open_price_orders();
        $bal = get_balances();
        $orphans = find_orphans($orders, $bal);
        if (!$orphans) { echo "nenhuma orfa para cancelar.\n"; break; }
        echo "Cancelando " . count($orphans) . " orfa(s)...\n";
        foreach ($orphans as $o) { cancel_order($o['id']); }
        echo "Log: ~/gate_cleanup_log.jsonl\n";
        break;

    case 'cancel':
        $ids = array_slice($argv, 2);
        if (!$ids) { fwrite(STDERR, "uso: php gate_cleanup.php cancel ID [ID...]\n"); exit(1); }
        foreach ($ids as $id) { cancel_order($id); }
        break;

    default:
        fwrite(STDERR, "comando desconhecido: $cmd (use list | orphans | cancel-orphans | cancel ID..)\n");
        exit(1);
}
