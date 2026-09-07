<?php
/**
 * Verificación de email: mueve una solicitud de `pendientes_verificacion/` a
 * `pendientes/` cuando el token del enlace coincide. Recién ahí el motor puede
 * gastar cuota con ella.
 */

declare(strict_types=1);

const COLA_DIR = '/home/seoagus/jet-maria-motor/out/solicitudes';

function pagina(string $titulo, string $cuerpo, int $code = 200): never {
    http_response_code($code);
    header('Content-Type: text/html; charset=utf-8');
    echo "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
       . "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
       . "<meta name=\"robots\" content=\"noindex, nofollow\">"
       . "<title>" . htmlspecialchars($titulo) . " · marIA.ar</title>"
       . "<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;"
       . "background:#F8F9FA;color:#202124;margin:0;line-height:1.6;padding:12vh 20px;text-align:center}"
       . ".box{max-width:460px;margin:0 auto;background:#fff;border:1px solid #E8EAED;"
       . "border-radius:18px;padding:32px;box-shadow:0 8px 24px rgba(0,0,0,.06)}"
       . "h1{font-size:1.4rem;margin:0 0 10px}p{color:#5F6368;margin:0 0 8px}"
       . "a{color:#1A73E8;font-weight:600}</style></head><body><div class=\"box\">"
       . "<h1>" . htmlspecialchars($titulo) . "</h1>" . $cuerpo
       . "<p style=\"margin-top:18px\"><a href=\"/indice-respuestas-ia/\">Ir al índice</a></p>"
       . "</div></body></html>";
    exit;
}

$id    = (string)($_GET['id'] ?? '');
$token = (string)($_GET['token'] ?? '');
if (!preg_match('/^[0-9A-Za-z:_.\-]+$/', $id) || $token === '') {
    pagina('Enlace inválido', '<p>El enlace de confirmación está incompleto.</p>', 400);
}

$src = COLA_DIR . '/pendientes_verificacion/' . basename($id) . '.json';

// ¿Ya estaba confirmada?
foreach (['pendientes', 'procesadas'] as $sub) {
    if (is_file(COLA_DIR . "/$sub/" . basename($id) . '.json')) {
        pagina('Pedido ya confirmado', '<p>Este pedido ya estaba confirmado. Lo estamos procesando.</p>');
    }
}
if (is_file(COLA_DIR . '/rechazadas/' . basename($id) . '.json')) {
    pagina('Pedido cerrado', '<p>Este pedido no puede procesarse (fuera de los límites de la versión piloto).</p>', 410);
}
if (!is_file($src)) {
    pagina('Pedido no encontrado', '<p>No encontramos ese pedido. Puede haber vencido; volvé a enviarlo.</p>', 404);
}

$reg = json_decode((string)file_get_contents($src), true);
if (!is_array($reg) || !hash_equals((string)($reg['token'] ?? ''), $token)) {
    pagina('Enlace inválido', '<p>El token de confirmación no coincide.</p>', 403);
}

$reg['verificada_utc'] = gmdate('Y-m-d\TH:i:s+00:00');
$reg['estado'] = 'pendiente';

$dst = COLA_DIR . '/pendientes/' . basename($id) . '.json';
if (!is_dir(dirname($dst))) { @mkdir(dirname($dst), 0770, true); }
if (file_put_contents($dst, json_encode($reg, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE), LOCK_EX) === false) {
    pagina('Error', '<p>No pudimos confirmar el pedido. Probá de nuevo en un rato.</p>', 500);
}
@unlink($src);

pagina('Pedido confirmado ✓',
    '<p>Listo. Tu pedido para <strong>' . htmlspecialchars($reg['empresa']) . '</strong> '
  . 'entró a la cola. Cuando la corrida esté lista te llega el informe por email.</p>');
