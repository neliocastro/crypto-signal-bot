<?php
/**
 * agent_gate.php - PORTEIRO DO ACESSO DO AGENTE AO SERVIDOR (D-042, 2026-10-21). SO LEITURA.
 * --------------------------------------------------------------------------
 * A chave SSH do agente (gerada no Mac do usuario) e autorizada no authorized_keys do
 * ineocom com `restrict,command="/usr/local/bin/php .../agent_gate.php"`: TODA conexao
 * com essa chave cai aqui, qualquer que seja o comando pedido. O comando pedido chega em
 * $SSH_ORIGINAL_COMMAND e so e aceito se for EXATAMENTE uma das acoes do menu abaixo.
 * Sem shell, sem argumentos, sem escrita (exceto o proprio agent_gate.log).
 *
 *   help      lista as acoes
 *   status    ultimas linhas dos logs do trigger, watchdog, PAXG e error_log + estados
 *   hashes    bytes, linhas e sha256 dos arquivos do bot no servidor (paridade com o Git)
 *   crontab   crontab -l do ineocom
 *   env-keys  so os NOMES das chaves do .env de segredos (nunca os valores)
 *   http      relay deve dar 401; arquivos da pasta publica devem dar 403 (D-040)
 *   resumo    status + hashes + http numa conexao so (D-045; P-20: muitas conexoes bloqueiam a porta 22)
 *
 * Nunca le nem imprime valor de segredo. Nunca cria, altera ou cancela ordem.
 * Rollback: apagar a linha da chave no /home/ineocom/.ssh/authorized_keys.
 */

declare(strict_types=1);

$AG = [
    'bin'    => '/home/ineocom/cryptosignals/bin',
    'pub'    => '/home/ineocom/public_html/cryptosignals',
    'env'    => '/home/ineocom/cryptosignals/secrets/.env',
    'url'    => 'https://ineo.com.br/cryptosignals',
];

const AG_ACOES = ['help', 'status', 'hashes', 'crontab', 'env-keys', 'http', 'resumo'];

// ---------------------------- funcoes puras (testaveis) ----------------------------

/** Acao valida ou null. So aceita o nome exato (sem espacos internos, argumentos ou separadores). */
function ag_acao(?string $cmd): ?string {
    if ($cmd === null) return 'help';
    $c = trim($cmd);
    if ($c === '') return 'help';
    return in_array($c, AG_ACOES, true) ? $c : null;
}

/** Mascara qualquer coisa com cara de segredo antes de sair (defesa extra: nada aqui deveria ter segredo). */
function ag_mascara(string $s): string {
    $s = preg_replace('/(github_pat_|ghp_|gho_|ghs_)[A-Za-z0-9_]+/', '$1***', $s);
    $s = preg_replace('/(Bearer\s+)[A-Za-z0-9._\-]+/i', '$1***', $s);
    $s = preg_replace('/(?<![0-9])\d{6,12}:[A-Za-z0-9_\-]{30,}/', '***token-telegram***', $s);
    return preg_replace('/((?:SECRET|TOKEN|KEY|PAT|PASS)[A-Z_]*\s*=\s*)\S+/i', '$1***', $s);
}

/** Ultimas $n linhas de um texto (sem a quebra final). */
function ag_ultimas(string $texto, int $n): array {
    $linhas = preg_split('/\r?\n/', rtrim($texto, "\r\n"));
    if ($linhas === [''] ) return [];
    return array_slice($linhas, -$n);
}

/** Linhas "data  tamanho  nome" de uma listagem [nome => [tamanho, mtime]], em ordem de nome. */
function ag_formatar_lista(array $itens): array {
    ksort($itens, SORT_STRING);
    $out = [];
    foreach ($itens as $nome => [$tam, $mtime]) {
        $out[] = sprintf('%s  %9d  %s', gmdate('Y-m-d H:i', (int)$mtime), (int)$tam, $nome);
    }
    return $out;
}

/** Lista de arquivos conferidos pela acao hashes (caminhos fixos). */
function ag_arquivos_hash(array $AG): array {
    return [
        $AG['pub'] . '/execute.php',
        $AG['pub'] . '/watchdog_scan.php',
        $AG['pub'] . '/.htaccess',
        $AG['bin'] . '/trigger_scan.php',
        $AG['bin'] . '/agent_gate.php',
    ];
}

// ---------------------------- acoes (leitura) ----------------------------

function ag_tail_arquivo(string $f, int $n): string {
    if (!is_file($f)) return "  (nao existe)\n";
    $tam = (int)filesize($f);
    $fh = fopen($f, 'rb');
    if (!$fh) return "  (sem leitura)\n";
    fseek($fh, max(0, $tam - 16384));
    $chunk = (string)stream_get_contents($fh);
    fclose($fh);
    $out = '';
    foreach (ag_ultimas($chunk, $n) as $l) $out .= '  ' . substr($l, 0, 300) . "\n";
    return $out;
}

function ag_lista_pasta(string $dir): string {
    $nomes = @scandir($dir);
    if ($nomes === false) return "  (sem leitura)\n";
    $itens = [];
    foreach ($nomes as $n) {
        if ($n === '.' || $n === '..') continue;
        $st = @stat($dir . '/' . $n);
        if ($st !== false) $itens[$n] = [$st['size'], $st['mtime']];
    }
    $o = '';
    foreach (ag_formatar_lista($itens) as $l) $o .= '  ' . $l . "\n";
    return $o;
}

function ag_status(array $AG): string {
    $o = '';
    foreach ([[$AG['bin'] . '/trigger_scan.log', 5], [$AG['pub'] . '/watchdog_cron.log', 4],
              [$AG['pub'] . '/paxg_cron.log', 4], [$AG['pub'] . '/error_log', 5],
              [$AG['bin'] . '/agent_gate.log', 5]] as [$f, $n]) {
        $o .= "== $f (ultimas $n)\n" . ag_tail_arquivo($f, $n);
    }
    foreach ([$AG['bin'] . '/.trigger_state.json', $AG['pub'] . '/.watchdog_state.json'] as $f) {
        $o .= "== $f\n  " . (is_file($f) ? trim((string)file_get_contents($f)) : '(nao existe)') . "\n";
    }
    foreach (['.paxg_pause' => $AG['pub'], '.watchdog_pause' => $AG['pub'], '.trigger_pause' => $AG['bin']] as $p => $d) {
        $o .= "== pausa $p: " . (file_exists("$d/$p") ? 'ATIVA' : 'nao') . "\n";
    }
    $o .= "== arquivos em " . $AG['pub'] . " (UTC)\n" . ag_lista_pasta($AG['pub']);
    return $o;
}

function ag_hashes(array $AG): string {
    $o = '';
    foreach (ag_arquivos_hash($AG) as $f) {
        if (!is_file($f)) { $o .= "AUSENTE  $f\n"; continue; }
        $txt = (string)file_get_contents($f);
        $o .= sprintf("%s  %6d bytes  %4d linhas  %s\n", hash('sha256', $txt), strlen($txt), substr_count($txt, "\n"), $f);
    }
    return $o;
}

function ag_crontab(): string {
    $r = shell_exec('crontab -l 2>&1');
    return is_string($r) ? $r : "(falha ao ler o crontab)\n";
}

function ag_env_keys(array $AG): string {
    $e = @parse_ini_file($AG['env']);
    if ($e === false) return "ERRO DE PARSE ou .env ausente\n";
    return implode(', ', array_keys($e)) . "\n";
}

function ag_http_code(string $url): int {
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 15, CURLOPT_NOBODY => false]);
    curl_exec($ch);
    $h = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return $h;
}

function ag_http(array $AG): string {
    // So GET em arquivos inofensivos; NUNCA em gerar_teste_*.php (compram de verdade).
    $o = sprintf("execute.php -> %d (esperado 401)\n", ag_http_code($AG['url'] . '/execute.php'));
    foreach (['watchdog_scan.php', 'paxg_cron.log', 'execution_log.jsonl', 'error_log'] as $f) {
        $o .= sprintf("%s -> %d (esperado 403)\n", $f, ag_http_code($AG['url'] . '/' . $f));
    }
    return $o;
}

function ag_main(array $AG): int {
    $pedido = getenv('SSH_ORIGINAL_COMMAND');
    $pedido = ($pedido === false) ? null : $pedido;
    $acao = ag_acao($pedido);
    $quem = (string)(getenv('SSH_CLIENT') ?: 'local');
    file_put_contents($AG['bin'] . '/agent_gate.log', sprintf("%s  %s  pedido=%s  %s\n", gmdate('c'),
        explode(' ', $quem)[0], substr(preg_replace('/\s+/', ' ', (string)$pedido), 0, 120),
        $acao === null ? 'RECUSADO' : 'ok'), FILE_APPEND | LOCK_EX);
    if ($acao === null) {
        fwrite(STDERR, "Recusado. Acoes permitidas: " . implode(', ', AG_ACOES) . "\n");
        return 2;
    }
    switch ($acao) {
        case 'help':     $out = "Acoes: " . implode(', ', AG_ACOES) . "\n"; break;
        case 'status':   $out = ag_status($AG); break;
        case 'hashes':   $out = ag_hashes($AG); break;
        case 'crontab':  $out = ag_crontab(); break;
        case 'env-keys': $out = ag_env_keys($AG); break;
        case 'http':     $out = ag_http($AG); break;
        default:         $out = "##### status\n" . ag_status($AG) . "##### hashes\n" . ag_hashes($AG)
                              . "##### http\n" . ag_http($AG); break;
    }
    echo ag_mascara($out);
    return 0;
}

if (PHP_SAPI === 'cli' && !defined('AGENT_GATE_NO_MAIN')) {
    exit(ag_main($AG));
}
