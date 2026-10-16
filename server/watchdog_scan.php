<?php
/**
 * watchdog_scan.php - WATCHDOG EXTERNO do scan + falhas do cron PAXG (D-037, 2026-10-15).
 * --------------------------------------------------------------------------
 * Roda de hora em hora no crontab do ineocom, FORA do GitHub Actions. Cobre o buraco
 * do bot/watchdog.py, que so roda dentro de um scan (parada total = silencio total).
 *
 *   1) SCAN PARADO: le state/runtime_config.json do main (raw.githubusercontent.com).
 *      Se last_scan_utc tiver mais de $MAX_GAP_MIN (DND: dnd_interval_min + 30) e o bot
 *      nao estiver pausado -> alerta no Telegram. Repete no maximo a cada
 *      $REALERT_H horas enquanto durar; avisa 1x quando o scan voltar.
 *      Falha ao ler o estado 3 vezes seguidas -> alerta proprio.
 *   2) CRON PAXG: linhas NOVAS com "FALHA na compra" no paxg_cron.log -> alerta
 *      (P-16: o cron falhou por meses sem aviso). Na 1a execucao so marca a posicao
 *      do log, sem alertar o historico antigo.
 *
 * So le e avisa: NUNCA cria, altera ou cancela ordem. Nao toca no execute.php.
 * Segredos: TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no .env de segredos (fora da web root).
 * O token NUNCA vai para log nem para a saida.
 *
 * Kill-switch: crie .watchdog_pause neste diretorio (ou comente a linha do crontab).
 *
 * USO (sempre com o CLI: /usr/local/bin/php, P-03):
 *   php watchdog_scan.php                  # modo cron
 *   php watchdog_scan.php --dry            # mostra a decisao; nao envia, nao grava estado
 *   php watchdog_scan.php --test-telegram  # envia 1 mensagem de teste (valida token/chat)
 */

declare(strict_types=1);

$WD = [
    'dir'          => __DIR__,
    'env_file'     => '/home/ineocom/cryptosignals/secrets/.env',
    'state_url'    => 'https://raw.githubusercontent.com/neliocastro/crypto-signal-bot/main/state/runtime_config.json',
    'max_gap_min'  => 60,
    'dnd_extra'    => 30,
    'realert_h'    => 3,
    'fetch_fail_n' => 3,
];

// ---------------------------- funcoes puras (testaveis) ----------------------------

function wd_parse_ts(?string $iso): ?int {
    if ($iso === null || $iso === '') return null;
    $t = strtotime($iso);
    return $t === false ? null : $t;
}

/** Limite efetivo em minutos (respeita o DND, como o bot/watchdog.py). */
function wd_limit_min(array $cfg, int $max_gap_min, int $dnd_extra): int {
    $limit = $max_gap_min;
    if (!empty($cfg['dnd_enabled'])) {
        $limit = max($limit, (int)($cfg['dnd_interval_min'] ?? 60) + $dnd_extra);
    }
    return $limit;
}

/**
 * Decide o que fazer com o scan. Retorna ['action' => ok|alert|still_down|recovered|paused|no_data,
 * 'gap_min' => float|null, 'limit' => int].
 * $st = estado do watchdog (scan_down_since, last_alert_ts).
 */
function wd_decide_scan(array $cfg, array $st, int $now, int $max_gap_min, int $dnd_extra, int $realert_h): array {
    $limit = wd_limit_min($cfg, $max_gap_min, $dnd_extra);
    if (!empty($cfg['paused'])) return ['action' => 'paused', 'gap_min' => null, 'limit' => $limit];
    $last = wd_parse_ts($cfg['last_scan_utc'] ?? null);
    if ($last === null) return ['action' => 'no_data', 'gap_min' => null, 'limit' => $limit];
    $gap = ($now - $last) / 60.0;
    $down = !empty($st['scan_down_since']);
    if ($gap <= $limit) {
        return ['action' => $down ? 'recovered' : 'ok', 'gap_min' => $gap, 'limit' => $limit];
    }
    $last_alert = (int)($st['last_alert_ts'] ?? 0);
    if (!$down || ($now - $last_alert) >= $realert_h * 3600) {
        return ['action' => 'alert', 'gap_min' => $gap, 'limit' => $limit];
    }
    return ['action' => 'still_down', 'gap_min' => $gap, 'limit' => $limit];
}

/**
 * Le o paxg_cron.log a partir de $offset. Retorna [novo_offset, linhas_FALHA_novas, primeira_vez].
 * Primeira execucao ($offset === null): so marca o fim do arquivo, sem alertar o historico.
 * Log rotacionado/truncado (tamanho < offset): rele do inicio.
 */
function wd_scan_paxg_log(string $file, ?int $offset): array {
    clearstatcache(true, $file);                 // tamanho atual, sem cache de stat
    if (!is_file($file)) return [$offset ?? 0, [], false];
    $size = (int)filesize($file);
    if ($offset === null) return [$size, [], true];
    if ($size < $offset) $offset = 0;
    if ($size === $offset) return [$offset, [], false];
    $fh = fopen($file, 'rb');
    if (!$fh) return [$offset, [], false];
    fseek($fh, $offset);
    $chunk = (string)stream_get_contents($fh);
    fclose($fh);
    $falhas = [];
    foreach (preg_split('/\r?\n/', $chunk) as $l) {
        if (strpos($l, 'FALHA na compra') !== false) $falhas[] = $l;
    }
    return [$size, $falhas, false];
}

function wd_msg_down(float $gap_min, int $limit, array $cfg): string {
    return "\u{26A0}\u{FE0F} WATCHDOG EXTERNO (servidor): o scan esta PARADO ha " . (int)round($gap_min) .
        " min (limite " . $limit . " min).\nUltimo scan: " . ($cfg['last_scan_utc'] ?? '?') . " UTC.\n" .
        "Verificar: Actions do repo (main.yml), cron do servidor e o SELF_DISPATCH_PAT.\n" .
        "Stops e TPs ja criados seguem ativos na Gate; o que para e entrada, trailing, OCO e renovacao de SL.";
}

function wd_msg_recovered(float $gap_min): string {
    return "\u{2705} WATCHDOG EXTERNO: o scan voltou a rodar (ultimo ha " . (int)round($gap_min) . " min).";
}

function wd_msg_paxg(array $falhas): string {
    $n = count($falhas);
    $ex = substr(preg_replace('/\s+/', ' ', $falhas[$n - 1]), 0, 300);
    return "\u{1F6A8} CRON PAXG: " . $n . " compra(s) com FALHA desde a ultima checagem.\nUltima: " . $ex .
        "\nVer paxg_cron.log no servidor (docs/operacao.md, secao 4).";
}

// ---------------------------- efeitos (rede, arquivos) ----------------------------

function wd_log(string $dir, string $msg): void {
    file_put_contents($dir . '/watchdog_cron.log', gmdate('c') . '  ' . $msg . "\n", FILE_APPEND | LOCK_EX);
}

function wd_load_state(string $dir): array {
    $f = $dir . '/.watchdog_state.json';
    if (!is_file($f)) return [];
    $d = json_decode((string)file_get_contents($f), true);
    return is_array($d) ? $d : [];
}

function wd_save_state(string $dir, array $st): void {
    file_put_contents($dir . '/.watchdog_state.json', json_encode($st), LOCK_EX);
}

function wd_fetch_cfg(string $url): ?array {
    $ch = curl_init($url . '?t=' . time());
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 15, CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_HTTPHEADER => ['User-Agent: cryptosignals-watchdog/1.0', 'Cache-Control: no-cache']]);
    $r = curl_exec($ch);
    $h = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($r === false || $h !== 200) return null;
    $d = json_decode((string)$r, true);
    return is_array($d) ? $d : null;
}

/** Envia ao Telegram e confere HTTP 200 + ok:true (P-09: run verde != passo funcionou). */
function wd_telegram(string $token, string $chat, string $text): array {
    $ch = curl_init('https://api.telegram.org/bot' . $token . '/sendMessage');
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 15, CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => http_build_query(['chat_id' => $chat, 'text' => $text, 'disable_web_page_preview' => 'true'])]);
    $r = curl_exec($ch);
    $h = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    $d = is_string($r) ? json_decode($r, true) : null;
    $ok = ($h === 200 && is_array($d) && !empty($d['ok']));
    return [$ok, $h, is_array($d) ? (string)($d['description'] ?? '') : ''];
}

function wd_main(array $WD, array $argv): int {
    $dir = $WD['dir'];
    $dry = in_array('--dry', $argv, true);
    $test = in_array('--test-telegram', $argv, true);

    if (!$test && file_exists($dir . '/.watchdog_pause')) {
        wd_log($dir, 'PAUSADO (.watchdog_pause existe) - nada feito');
        fwrite(STDERR, "PAUSADO: remova .watchdog_pause para reativar\n");
        return 0;
    }
    $env = @parse_ini_file($WD['env_file']) ?: [];
    $token = trim((string)($env['TELEGRAM_TOKEN'] ?? ''));
    $chat = trim((string)($env['TELEGRAM_CHAT_ID'] ?? ''));
    $send = function (string $text) use ($token, $chat, $dir, $dry): bool {
        if ($dry) { fwrite(STDERR, "[--dry] enviaria:\n$text\n"); return true; }
        if ($token === '' || $chat === '') { wd_log($dir, 'ERRO: TELEGRAM_TOKEN/CHAT_ID ausentes no .env'); return false; }
        [$ok, $h, $desc] = wd_telegram($token, $chat, $text);
        wd_log($dir, sprintf('telegram ok=%s http=%d %s', $ok ? 'SIM' : 'NAO', $h, $desc));
        return $ok;
    };

    if ($test) {
        $ok = $send("\u{1F9EA} Teste do watchdog externo (servidor): Telegram OK.");
        fwrite(STDERR, $ok ? "Telegram OK\n" : "FALHA no Telegram (ver watchdog_cron.log)\n");
        return $ok ? 0 : 2;
    }

    $st = wd_load_state($dir);
    $now = time();
    $exit = 0;

    // ---- 1) scan parado? ----
    $cfg = wd_fetch_cfg($WD['state_url']);
    if ($cfg === null) {
        $st['fetch_fails'] = (int)($st['fetch_fails'] ?? 0) + 1;
        wd_log($dir, 'ERRO ao ler runtime_config.json (falha ' . $st['fetch_fails'] . ' seguida)');
        if ($st['fetch_fails'] === $WD['fetch_fail_n']) {
            $send("\u{26A0}\u{FE0F} WATCHDOG EXTERNO: nao consigo ler o estado do bot no GitHub ha " .
                $WD['fetch_fail_n'] . " checagens seguidas. Conferir o repositorio e a rede do servidor.");
        }
        $exit = 1;
    } else {
        $st['fetch_fails'] = 0;
        $d = wd_decide_scan($cfg, $st, $now, $WD['max_gap_min'], $WD['dnd_extra'], $WD['realert_h']);
        $gap = $d['gap_min'] === null ? '-' : sprintf('%.1f', $d['gap_min']);
        wd_log($dir, sprintf('scan: %s (gap=%smin, limite=%dmin)', $d['action'], $gap, $d['limit']));
        if ($d['action'] === 'alert') {
            if ($send(wd_msg_down($d['gap_min'], $d['limit'], $cfg))) {
                $st['scan_down_since'] = $st['scan_down_since'] ?? $now;
                $st['last_alert_ts'] = $now;
            }
        } elseif ($d['action'] === 'recovered') {
            if ($send(wd_msg_recovered($d['gap_min']))) {
                unset($st['scan_down_since'], $st['last_alert_ts']);
            }
        }
    }

    // ---- 2) falhas novas do cron PAXG ----
    [$off, $falhas, $primeira] = wd_scan_paxg_log($dir . '/paxg_cron.log',
        array_key_exists('paxg_log_offset', $st) ? (int)$st['paxg_log_offset'] : null);
    if ($primeira) wd_log($dir, "paxg: primeira execucao, offset marcado em $off (historico nao alertado)");
    $paxg_ok = true;
    if ($falhas) {
        wd_log($dir, 'paxg: ' . count($falhas) . ' FALHA(s) nova(s)');
        $paxg_ok = $send(wd_msg_paxg($falhas));
    }
    if ($paxg_ok) $st['paxg_log_offset'] = $off;   // falhou o envio -> tenta de novo na proxima hora

    if (!$dry) wd_save_state($dir, $st);
    return $exit;
}

if (PHP_SAPI === 'cli' && !defined('WATCHDOG_NO_MAIN')) {
    exit(wd_main($WD, $argv));
}
