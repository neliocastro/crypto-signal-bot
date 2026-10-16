<?php
/**
 * test_watchdog_scan.php - logica pura do server/watchdog_scan.php (D-037, 2026-10-15).
 * Sem rede e sem Telegram: so as funcoes de decisao e a leitura incremental do log.
 *
 * COMO RODAR:  php tests/test_watchdog_scan.php   (sai com codigo 0 se ok)
 */
declare(strict_types=1);
define('WATCHDOG_NO_MAIN', true);
require __DIR__ . '/../server/watchdog_scan.php';

$falhas = 0;
function t(string $nome, callable $fn): void {
    global $falhas;
    try { $fn(); echo "PASS  $nome\n"; }
    catch (Throwable $e) { $falhas++; echo "FAIL  $nome -> " . $e->getMessage() . "\n"; }
}
function eq($a, $b, string $msg = ''): void {
    if ($a !== $b) throw new Exception($msg . ' esperado ' . var_export($b, true) . ', veio ' . var_export($a, true));
}

$NOW = strtotime('2026-10-15T12:00:00Z');
$cfg = fn(int $min_atras, array $extra = []) => array_merge(
    ['last_scan_utc' => gmdate('c', $NOW - $min_atras * 60), 'paused' => false, 'dnd_enabled' => false], $extra);

t('scan_ok_dentro_do_limite', function () use ($cfg, $NOW) {
    eq(wd_decide_scan($cfg(59), [], $NOW, 60, 30, 3)['action'], 'ok');
});
t('scan_parado_alerta', function () use ($cfg, $NOW) {
    $d = wd_decide_scan($cfg(61), [], $NOW, 60, 30, 3);
    eq($d['action'], 'alert'); eq($d['limit'], 60);
});
t('nao_repete_antes_de_3h', function () use ($cfg, $NOW) {
    $st = ['scan_down_since' => $NOW - 7200, 'last_alert_ts' => $NOW - 2 * 3600];
    eq(wd_decide_scan($cfg(180), $st, $NOW, 60, 30, 3)['action'], 'still_down');
});
t('repete_depois_de_3h', function () use ($cfg, $NOW) {
    $st = ['scan_down_since' => $NOW - 4 * 3600, 'last_alert_ts' => $NOW - 3 * 3600];
    eq(wd_decide_scan($cfg(240), $st, $NOW, 60, 30, 3)['action'], 'alert');
});
t('avisa_quando_volta', function () use ($cfg, $NOW) {
    $st = ['scan_down_since' => $NOW - 7200, 'last_alert_ts' => $NOW - 3600];
    eq(wd_decide_scan($cfg(5), $st, $NOW, 60, 30, 3)['action'], 'recovered');
});
t('pausado_nao_alerta', function () use ($cfg, $NOW) {
    eq(wd_decide_scan($cfg(600, ['paused' => true]), [], $NOW, 60, 30, 3)['action'], 'paused');
});
t('dnd_amplia_o_limite', function () use ($cfg, $NOW) {
    $c = $cfg(80, ['dnd_enabled' => true, 'dnd_interval_min' => 60]);
    $d = wd_decide_scan($c, [], $NOW, 60, 30, 3);
    eq($d['limit'], 90); eq($d['action'], 'ok');
});
t('sem_last_scan', function () use ($NOW) {
    eq(wd_decide_scan(['last_scan_utc' => null], [], $NOW, 60, 30, 3)['action'], 'no_data');
});

t('paxg_primeira_execucao_nao_alerta_historico', function () {
    $f = tempnam(sys_get_temp_dir(), 'paxg');
    file_put_contents($f, "2026-10-14T14:00:07+00:00  FALHA na compra: x\n");
    [$off, $falhas, $primeira] = wd_scan_paxg_log($f, null);
    eq($primeira, true); eq($falhas, []); eq($off, filesize($f));
    unlink($f);
});
t('paxg_so_falhas_novas', function () {
    $f = tempnam(sys_get_temp_dir(), 'paxg');
    file_put_contents($f, "antiga FALHA na compra: a\n");
    $off0 = filesize($f);
    file_put_contents($f, "skip: RSI4h=48\nFALHA na compra: b\nFALHA ao comprar (ver paxg_cron.log)\nCOMPRA OK: c\n", FILE_APPEND);
    [$off, $falhas] = wd_scan_paxg_log($f, $off0);
    eq(count($falhas), 1); eq($falhas[0], 'FALHA na compra: b'); eq($off, filesize($f));
    [, $de_novo] = wd_scan_paxg_log($f, $off);
    eq($de_novo, []);
    unlink($f);
});
t('paxg_log_rotacionado_rele_do_inicio', function () {
    $f = tempnam(sys_get_temp_dir(), 'paxg');
    file_put_contents($f, "FALHA na compra: nova\n");
    [, $falhas] = wd_scan_paxg_log($f, 999999);
    eq(count($falhas), 1);
    unlink($f);
});
t('paxg_log_ausente', function () {
    eq(wd_scan_paxg_log('/nao/existe.log', 10), [10, [], false]);
});
t('mensagens_sem_segredo_e_com_numeros', function () use ($cfg) {
    $m = wd_msg_down(125.4, 60, $cfg(125));
    if (strpos($m, '125 min') === false || strpos($m, 'limite 60') === false) throw new Exception($m);
    if (stripos($m, 'token') !== false) throw new Exception('mensagem cita token');
    $p = wd_msg_paxg(['l1', "FALHA na compra: RSI4h=26   resp=500"]);
    if (strpos($p, '2 compra(s)') === false || strpos($p, 'RSI4h=26 resp=500') === false) throw new Exception($p);
});

exit($falhas ? 1 : 0);
