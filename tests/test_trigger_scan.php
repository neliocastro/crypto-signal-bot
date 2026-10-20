<?php
/**
 * test_trigger_scan.php - logica pura do server/trigger_scan.php (D-039, 2026-10-20).
 * Sem rede, sem GitHub e sem Telegram: so a decisao de alerta e as mensagens.
 *
 * COMO RODAR:  php tests/test_trigger_scan.php   (sai com codigo 0 se ok)
 */
declare(strict_types=1);
define('TRIGGER_NO_MAIN', true);
require __DIR__ . '/../server/trigger_scan.php';

$falhas = 0;
function t(string $nome, callable $fn): void {
    global $falhas;
    try { $fn(); echo "PASS  $nome\n"; }
    catch (Throwable $e) { $falhas++; echo "FAIL  $nome -> " . $e->getMessage() . "\n"; }
}
function eq($a, $b, string $msg = ''): void {
    if ($a !== $b) throw new Exception($msg . ' esperado ' . var_export($b, true) . ', veio ' . var_export($a, true));
}

$NOW = strtotime('2026-10-20T12:00:00Z');

t('sucesso_sem_alerta', function () use ($NOW) {
    [$st, $acao] = tr_decide([], true, $NOW, 3, 3);
    eq($acao, 'none'); eq($st['fails'], 0); eq($st['alerted'], false);
});
t('duas_falhas_ainda_nao_alerta', function () use ($NOW) {
    [$st, $acao] = tr_decide(['fails' => 1], false, $NOW, 3, 3);
    eq($acao, 'none'); eq($st['fails'], 2);
});
t('terceira_falha_alerta', function () use ($NOW) {
    [$st, $acao] = tr_decide(['fails' => 2], false, $NOW, 3, 3);
    eq($acao, 'alert'); eq($st['fails'], 3);
});
t('ja_alertado_nao_repete_antes_de_3h', function () use ($NOW) {
    $st0 = ['fails' => 10, 'alerted' => true, 'last_alert_ts' => $NOW - 2 * 3600];
    eq(tr_decide($st0, false, $NOW, 3, 3)[1], 'none');
});
t('ja_alertado_repete_depois_de_3h', function () use ($NOW) {
    $st0 = ['fails' => 40, 'alerted' => true, 'last_alert_ts' => $NOW - 3 * 3600];
    eq(tr_decide($st0, false, $NOW, 3, 3)[1], 'alert');
});
t('alerta_que_falhou_tenta_de_novo', function () use ($NOW) {
    // envio falhou: o chamador nao grava alerted -> a proxima falha alerta de novo
    eq(tr_decide(['fails' => 3], false, $NOW, 3, 3)[1], 'alert');
});
t('volta_depois_de_alerta_avisa', function () use ($NOW) {
    [$st, $acao] = tr_decide(['fails' => 7, 'alerted' => true, 'last_alert_ts' => $NOW - 600], true, $NOW, 3, 3);
    eq($acao, 'recovered'); eq($st['fails'], 0); eq($st['alerted'], false);
});
t('volta_sem_alerta_previo_nao_avisa', function () use ($NOW) {
    eq(tr_decide(['fails' => 2], true, $NOW, 3, 3)[1], 'none');
});
t('dicas_por_codigo', function () {
    eq(tr_hint(401), 'SELF_DISPATCH_PAT expirado/revogado ou errado no .env');
    eq(tr_hint(403), 'token sem permissao Actions RW');
    eq(tr_hint(500), 'erro do GitHub (costuma ser passageiro)');
    eq(tr_hint(0), 'sem resposta (rede ou DNS do servidor)');
});
t('mensagem_de_falha_sem_segredo', function () {
    $m = tr_msg_fail(3, 401);
    if (strpos($m, '3 disparos') === false || strpos($m, 'HTTP 401') === false) throw new Exception($m);
    if (preg_match('/github_pat_|ghp_|Bearer/i', $m)) throw new Exception('mensagem com cara de token');
});

exit($falhas ? 1 : 0);
