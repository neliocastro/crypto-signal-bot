<?php
/**
 * trigger_scan.php - DISPARO DO SCAN PELO SERVIDOR (D-039, 2026-10-20).
 * --------------------------------------------------------------------------
 * Roda a cada 5 min no crontab do ineocom e dispara o main.yml via workflow_dispatch.
 * E a perna independente da cadencia: se a corrente do proprio main.yml quebrar
 * (ex.: HTTP 500 do GitHub em 2026-10-19 23:30), este cron retoma os scans.
 * Substitui o trigger_scan.sh antigo (curl -s sem checar HTTP, token dentro do script,
 * log e crontab apontando para uma pasta inexistente: P-18).
 *
 *   - Token: SELF_DISPATCH_PAT no .env de segredos (fora da web root). NUNCA vai para log
 *     nem para a saida.
 *   - Sucesso = HTTP 204 (P-09: run verde != passo funcionou). Qualquer outro codigo e falha.
 *   - 3 falhas seguidas (~15 min) -> alerta no Telegram; repete no maximo a cada 3 h
 *     enquanto durar; avisa 1x quando voltar.
 *
 * So dispara o workflow: NUNCA cria, altera ou cancela ordem. Fica fora da pasta publica
 * (/home/ineocom/cryptosignals/bin/) e so roda pelo terminal.
 *
 * Kill-switch: crie .trigger_pause neste diretorio (ou comente a linha do crontab).
 *
 * USO (sempre com o CLI: /usr/local/bin/php, P-03):
 *   php trigger_scan.php          # modo cron
 *   php trigger_scan.php --dry    # confere config (token presente/ausente, sem mostrar); nao dispara
 */

declare(strict_types=1);

$TR = [
    'dir'       => __DIR__,
    'env_file'  => '/home/ineocom/cryptosignals/secrets/.env',
    'repo'      => 'neliocastro/crypto-signal-bot',
    'workflow'  => 'main.yml',
    'ref'       => 'main',
    'fail_n'    => 3,
    'realert_h' => 3,
];

// ---------------------------- funcoes puras (testaveis) ----------------------------

/**
 * Atualiza o estado apos um disparo e diz se deve avisar.
 * Retorna [novo_estado, acao] com acao em: none | alert | recovered.
 * O chamador so grava 'alerted'/'last_alert_ts' se o envio ao Telegram der certo.
 */
function tr_decide(array $st, bool $ok, int $now, int $fail_n, int $realert_h): array {
    $fails = (int)($st['fails'] ?? 0);
    $alerted = !empty($st['alerted']);
    if ($ok) {
        $novo = ['fails' => 0, 'alerted' => false, 'last_ok_ts' => $now];
        return [$novo, $alerted ? 'recovered' : 'none'];
    }
    $fails++;
    $novo = $st;
    $novo['fails'] = $fails;
    if ($fails < $fail_n) return [$novo, 'none'];
    $last_alert = (int)($st['last_alert_ts'] ?? 0);
    if (!$alerted || ($now - $last_alert) >= $realert_h * 3600) return [$novo, 'alert'];
    return [$novo, 'none'];
}

/** Dica do que significa o codigo HTTP (mesma tabela do main.yml). */
function tr_hint(int $code): string {
    switch ($code) {
        case 401: return 'SELF_DISPATCH_PAT expirado/revogado ou errado no .env';
        case 403: return 'token sem permissao Actions RW';
        case 404: return 'repo nao selecionado no token ou workflow inexistente';
        case 0:   return 'sem resposta (rede ou DNS do servidor)';
        default:  return $code >= 500 ? 'erro do GitHub (costuma ser passageiro)' : 'resposta inesperada';
    }
}

function tr_msg_fail(int $fails, int $code): string {
    return "\u{26A0}\u{FE0F} TRIGGER DO SERVIDOR: " . $fails . " disparos seguidos do main.yml falharam (ultimo: HTTP " .
        $code . ", " . tr_hint($code) . ").\nA cadencia agora depende so da corrente do proprio main.yml.\n" .
        "Ver trigger_scan.log no servidor (docs/operacao.md, secao 9).";
}

function tr_msg_recovered(int $fails_antes): string {
    return "\u{2705} TRIGGER DO SERVIDOR: disparo do main.yml voltou a funcionar (HTTP 204).";
}

// ---------------------------- efeitos (rede, arquivos) ----------------------------

function tr_log(string $dir, string $msg): void {
    file_put_contents($dir . '/trigger_scan.log', gmdate('c') . '  ' . $msg . "\n", FILE_APPEND | LOCK_EX);
}

function tr_load_state(string $dir): array {
    $f = $dir . '/.trigger_state.json';
    if (!is_file($f)) return [];
    $d = json_decode((string)file_get_contents($f), true);
    return is_array($d) ? $d : [];
}

function tr_save_state(string $dir, array $st): void {
    file_put_contents($dir . '/.trigger_state.json', json_encode($st), LOCK_EX);
}

/** POST workflow_dispatch. Retorna [codigo_http, trecho_da_resposta]. */
function tr_dispatch(string $token, string $repo, string $workflow, string $ref): array {
    $url = 'https://api.github.com/repos/' . $repo . '/actions/workflows/' . $workflow . '/dispatches';
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20, CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode(['ref' => $ref, 'inputs' => ['self_chain' => 'false']]),
        CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $token, 'Accept: application/vnd.github+json',
            'X-GitHub-Api-Version: 2022-11-28', 'User-Agent: cryptosignals-trigger/1.0']]);
    $r = curl_exec($ch);
    $h = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    $body = is_string($r) ? substr(preg_replace('/\s+/', ' ', $r), 0, 200) : '';
    return [$h, $body];
}

function tr_telegram(string $token, string $chat, string $text): bool {
    if ($token === '' || $chat === '') return false;
    $ch = curl_init('https://api.telegram.org/bot' . $token . '/sendMessage');
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 15, CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => http_build_query(['chat_id' => $chat, 'text' => $text, 'disable_web_page_preview' => 'true'])]);
    $r = curl_exec($ch);
    $h = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    $d = is_string($r) ? json_decode($r, true) : null;
    return $h === 200 && is_array($d) && !empty($d['ok']);
}

function tr_main(array $TR, array $argv): int {
    $dir = $TR['dir'];
    $dry = in_array('--dry', $argv, true);
    if (file_exists($dir . '/.trigger_pause')) {
        tr_log($dir, 'PAUSADO (.trigger_pause existe) - nada feito');
        return 0;
    }
    $env = @parse_ini_file($TR['env_file']) ?: [];
    $pat = trim((string)($env['SELF_DISPATCH_PAT'] ?? ''));
    $tg_token = trim((string)($env['TELEGRAM_TOKEN'] ?? ''));
    $tg_chat = trim((string)($env['TELEGRAM_CHAT_ID'] ?? ''));

    if ($dry) {
        fwrite(STDERR, 'SELF_DISPATCH_PAT: ' . ($pat === '' ? 'AUSENTE' : 'presente (' . strlen($pat) . ' caracteres)') . "\n");
        fwrite(STDERR, 'Telegram: ' . (($tg_token !== '' && $tg_chat !== '') ? 'configurado' : 'AUSENTE') . "\n");
        fwrite(STDERR, 'Estado: ' . json_encode(tr_load_state($dir)) . "\n[--dry] nada disparado.\n");
        return 0;
    }

    if ($pat === '') {
        [$code, $body] = [0, 'SELF_DISPATCH_PAT ausente no .env'];
    } else {
        [$code, $body] = tr_dispatch($pat, $TR['repo'], $TR['workflow'], $TR['ref']);
    }
    $ok = ($code === 204);
    tr_log($dir, $ok ? 'dispatch HTTP 204' : sprintf('FALHA dispatch HTTP %d (%s) %s', $code, tr_hint($code), $body));

    $st = tr_load_state($dir);
    [$novo, $acao] = tr_decide($st, $ok, time(), $TR['fail_n'], $TR['realert_h']);
    if ($acao === 'alert') {
        if (tr_telegram($tg_token, $tg_chat, tr_msg_fail((int)$novo['fails'], $code))) {
            $novo['alerted'] = true;
            $novo['last_alert_ts'] = time();
            tr_log($dir, 'alerta Telegram enviado');
        } else {
            tr_log($dir, 'ERRO: alerta Telegram NAO enviado');
        }
    } elseif ($acao === 'recovered') {
        if (tr_telegram($tg_token, $tg_chat, tr_msg_recovered((int)($st['fails'] ?? 0)))) {
            tr_log($dir, 'aviso de volta enviado');
        } else {
            $novo['alerted'] = true;   // tenta avisar a volta no proximo disparo ok
            tr_log($dir, 'ERRO: aviso de volta NAO enviado');
        }
    }
    tr_save_state($dir, $novo);
    return $ok ? 0 : 1;
}

if (PHP_SAPI === 'cli' && !defined('TRIGGER_NO_MAIN')) {
    exit(tr_main($TR, $argv));
}
