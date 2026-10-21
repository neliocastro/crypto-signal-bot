<?php
/**
 * test_agent_gate.php - logica pura do server/agent_gate.php (D-042, 2026-10-21).
 * O que importa provar: so passam as acoes exatas do menu e nada com cara de segredo sai.
 *
 * COMO RODAR:  php tests/test_agent_gate.php   (sai com codigo 0 se ok)
 */
declare(strict_types=1);
define('AGENT_GATE_NO_MAIN', true);
require __DIR__ . '/../server/agent_gate.php';

$falhas = 0;
function t(string $nome, callable $fn): void {
    global $falhas;
    try { $fn(); echo "PASS  $nome\n"; }
    catch (Throwable $e) { $falhas++; echo "FAIL  $nome -> " . $e->getMessage() . "\n"; }
}
function eq($a, $b, string $msg = ''): void {
    if ($a !== $b) throw new Exception($msg . ' esperado ' . var_export($b, true) . ', veio ' . var_export($a, true));
}

t('acoes_do_menu_passam', function () {
    foreach (['help', 'status', 'hashes', 'crontab', 'env-keys', 'http'] as $a) eq(ag_acao($a), $a, $a);
    eq(ag_acao('  status  '), 'status');
});
t('sem_comando_vira_help', function () {
    eq(ag_acao(null), 'help'); eq(ag_acao(''), 'help'); eq(ag_acao('   '), 'help');
});
t('qualquer_outra_coisa_e_recusada', function () {
    $ruins = ['cat /home/ineocom/cryptosignals/secrets/.env', 'status; cat .env', 'status && id', 'status | sh',
              'status $(id)', 'status `id`', "status\ncat .env", 'hashes extra', 'STATUS', 'env', 'env-keys -v',
              'bash', 'sh -c id', 'php -r "echo 1;"', 'crontab -e', 'crontab -r', 'rm -rf /', 'scp -t .', 'rsync --server'];
    foreach ($ruins as $r) eq(ag_acao($r), null, $r);
});
t('mascara_tokens', function () {
    $s = ag_mascara("x github_pat_11ABCDEFG0123456789_abcdefghijklmnop y ghp_abcdefghijklmnopqrstuvwxyz0123456789");
    if (preg_match('/github_pat_[A-Za-z0-9]|ghp_[A-Za-z0-9]/', $s)) throw new Exception($s);
    $b = ag_mascara('-H "Authorization: Bearer abc.def-123"');
    if (strpos($b, 'abc.def-123') !== false) throw new Exception($b);
    $tg = ag_mascara('bot1234567890:AAH-abcdefghijklmnopqrstuvwxyz012345/sendMessage');
    if (strpos($tg, 'AAH-abc') !== false) throw new Exception($tg);
    $env = ag_mascara("GATE_API_SECRET=abc123\nSELF_DISPATCH_PAT = xyz\nEXECUTION_HMAC_SECRET=q");
    if (preg_match('/abc123|xyz|=q/', $env)) throw new Exception($env);
});
t('mascara_preserva_o_resto', function () {
    eq(ag_mascara("EXECUTION_HMAC_SECRET, GATE_API_KEY, TELEGRAM_TOKEN\n"), "EXECUTION_HMAC_SECRET, GATE_API_KEY, TELEGRAM_TOKEN\n");
    $h = "05846d951f63bdab7715556d5942e07f3f3de5531e490966ddc3109f495eeb17    7987 bytes   179 linhas  /x/trigger_scan.php\n";
    eq(ag_mascara($h), $h);
    eq(ag_mascara("2026-10-21T00:30:04+00:00  dispatch HTTP 204\n"), "2026-10-21T00:30:04+00:00  dispatch HTTP 204\n");
});
t('ultimas_linhas', function () {
    eq(ag_ultimas("a\nb\nc\nd\n", 2), ['c', 'd']);
    eq(ag_ultimas("a\r\nb\r\n", 5), ['a', 'b']);
    eq(ag_ultimas('', 3), []);
});
t('arquivos_de_hash_sao_fixos_e_sem_segredo', function () {
    $AG = ['bin' => '/b', 'pub' => '/p', 'env' => '/e/.env', 'url' => 'u'];
    $fs = ag_arquivos_hash($AG);
    eq(count($fs), 7);
    foreach ($fs as $f) if (strpos($f, '.env') !== false || strpos($f, 'secrets') !== false) throw new Exception($f);
});

exit($falhas ? 1 : 0);
