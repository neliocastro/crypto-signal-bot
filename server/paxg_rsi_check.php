<?php
/**
 * paxg_rsi_check.php — CRON de ACUMULACAO automatica do PAXG (Caminho 1).
 * --------------------------------------------------------------------------
 * Roda de hora em hora (crontab). Compra $10 de PAXG SOMENTE quando:
 *   (1) RSI 4h(14) < 30   (sobrevenda)   E
 *   (2) passaram >= 12h desde a ultima compra automatica (cooldown)
 *
 * NAO calcula SL aqui: quem monta a ordem (com SL largo -15%, sem TP) e o
 * gerar_teste_paxg.php — este script so DECIDE se dispara.
 *
 * Kill-switch: comente a linha no crontab, ou crie o arquivo .paxg_pause
 * no mesmo diretorio (presenca do arquivo = pausado).
 *
 * USO:
 *   php paxg_rsi_check.php          # modo cron (decide e, se for o caso, compra)
 *   php paxg_rsi_check.php --dry    # so mostra o RSI e a decisao, NAO compra
 */

declare(strict_types=1);

$DIR          = __DIR__;
$PAIR         = 'PAXG_USDT';
$RSI_PERIOD   = 14;
$RSI_LIMIAR   = 30.0;      // compra se RSI < 30
$COOLDOWN_H   = 12;        // horas minimas entre compras
$NOTIONAL     = 10.0;      // $10 por acumulo (informativo; valor real esta no gerar_teste_paxg.php)
$BUY_SCRIPT   = $DIR . '/gerar_teste_paxg.php';
$LAST_BUY_F   = $DIR . '/.paxg_last_buy';     // timestamp epoch da ultima compra
$PAUSE_F      = $DIR . '/.paxg_pause';        // se existir, pausa tudo
$LOG_F        = $DIR . '/paxg_cron.log';

$DRY = in_array('--dry', $argv, true);

function logline(string $f, string $msg): void {
    file_put_contents($f, gmdate('c') . "  " . $msg . "\n", FILE_APPEND | LOCK_EX);
}

function http_get_json(string $url) {
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_HTTPHEADER     => ['User-Agent: paxg-cron/1.0', 'Accept: application/json'],
    ]);
    $r = curl_exec($ch);
    $h = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($r !== false && $h >= 200 && $h < 300) {
        $d = json_decode($r, true);
        if (is_array($d)) return $d;
    }
    return null;
}

// RSI de Wilder (mesma formula validada no sandbox)
function rsi_wilder(array $closes, int $period): ?float {
    $n = count($closes);
    if ($n < $period + 1) return null;
    $gain = 0.0; $loss = 0.0;
    for ($i = 1; $i <= $period; $i++) {
        $d = $closes[$i] - $closes[$i-1];
        if ($d >= 0) $gain += $d; else $loss += -$d;
    }
    $ag = $gain / $period; $al = $loss / $period;
    for ($i = $period + 1; $i < $n; $i++) {
        $d = $closes[$i] - $closes[$i-1];
        $g = $d > 0 ? $d : 0.0; $l = $d < 0 ? -$d : 0.0;
        $ag = ($ag * ($period - 1) + $g) / $period;
        $al = ($al * ($period - 1) + $l) / $period;
    }
    if ($al == 0.0) return 100.0;
    $rs = $ag / $al;
    return 100.0 - (100.0 / (1.0 + $rs));
}

// ---- 0) pausa manual? ----
if (file_exists($PAUSE_F)) {
    logline($LOG_F, "PAUSADO (.paxg_pause existe) - nada feito");
    fwrite(STDERR, "PAUSADO: remova $PAUSE_F para reativar\n");
    exit(0);
}

// ---- 1) busca candles 4h e calcula RSI ----
$k = http_get_json("https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={$PAIR}&interval=4h&limit=200");
if (!$k || !is_array($k) || count($k) < $RSI_PERIOD + 2) {
    logline($LOG_F, "ERRO: candles 4h indisponiveis - abortado (sem compra)");
    fwrite(STDERR, "ERRO ao ler candles 4h\n");
    exit(1);
}
// Gate.io: cada vela = [ts, vol_quote, close, high, low, open, ...]  -> close = idx 2
$closes = array_map(fn($c) => (float)$c[2], $k);
$rsi = rsi_wilder($closes, $RSI_PERIOD);
if ($rsi === null) {
    logline($LOG_F, "ERRO: RSI nulo - abortado");
    exit(1);
}

// ---- 2) cooldown ----
$now = time();
$last = file_exists($LAST_BUY_F) ? (int)trim((string)file_get_contents($LAST_BUY_F)) : 0;
$horas_desde = $last > 0 ? ($now - $last) / 3600.0 : 9999.0;
$cooldown_ok = $horas_desde >= $COOLDOWN_H;

$decisao = sprintf("RSI4h=%.2f (limiar<%.0f) | ult.compra ha %.1fh (cooldown %dh) | dispara=%s",
    $rsi, $RSI_LIMIAR, $horas_desde, $COOLDOWN_H,
    ($rsi < $RSI_LIMIAR && $cooldown_ok) ? 'SIM' : 'NAO');

fwrite(STDERR, "$decisao\n");

// ---- 3) decide ----
if ($rsi >= $RSI_LIMIAR) {
    logline($LOG_F, "skip: $decisao");
    exit(0);
}
if (!$cooldown_ok) {
    logline($LOG_F, "skip(cooldown): $decisao");
    exit(0);
}

// ---- 4) dispara a compra (a menos que --dry) ----
if ($DRY) {
    logline($LOG_F, "DRY: COMPRARIA -> $decisao");
    fwrite(STDERR, "[--dry] compraria \$$NOTIONAL de PAXG agora (RSI<30, cooldown ok)\n");
    exit(0);
}

$out = [];
$code = 0;
exec('php ' . escapeshellarg($BUY_SCRIPT) . ' 2>&1', $out, $code);
$resp = implode("\n", $out);
$ok = (strpos($resp, '"status": "filled"') !== false) || (strpos($resp, '"status":"filled"') !== false);

if ($ok) {
    file_put_contents($LAST_BUY_F, (string)$now, LOCK_EX);   // arma o cooldown
    logline($LOG_F, "COMPRA OK: $decisao | resp=filled");
    fwrite(STDERR, "COMPRA EXECUTADA (filled). cooldown de {$COOLDOWN_H}h armado.\n");
    echo $resp . "\n";
    exit(0);
} else {
    logline($LOG_F, "FALHA na compra: $decisao | resp(trunc)=" . substr(preg_replace('/\s+/', ' ', $resp), 0, 300));
    fwrite(STDERR, "FALHA ao comprar (ver paxg_cron.log)\n");
    echo $resp . "\n";
    exit(2);
}
