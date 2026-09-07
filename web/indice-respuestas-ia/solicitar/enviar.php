<?php
/**
 * Endpoint de la cola del Índice de Visibilidad en Respuestas de IA.
 *
 * NO consulta a Gemini. Escribe un archivo de trabajo JSON en la cola en disco
 * (`out/solicitudes/pendientes_verificacion/`) y manda un email de confirmación.
 * El motor (`maria-respuestas cola`) es quien procesa la cola, a mano o por cron.
 *
 * Control de gasto y de abuso (obligatorio — el plan lo exige para un formulario
 * público que consume cuota por request):
 *   - lista blanca de industrias de la v1;
 *   - tope por IP y por día;
 *   - tope duro global de solicitudes nuevas por día;
 *   - verificación de email antes de que el motor gaste cuota.
 *
 * Sin dependencias: solo la stdlib de PHP.
 */

declare(strict_types=1);

// --- configuración ---------------------------------------------------------
const COLA_DIR       = '/home/seoagus/jet-maria-motor/out/solicitudes';
const INDUSTRIAS     = ['aviación ejecutiva'];        // debe coincidir con solicitudes.py
const TOPE_POR_IP    = 3;                             // solicitudes/IP/día
const TOPE_GLOBAL    = 40;                            // solicitudes nuevas/día (todas las IP)
const BASE_URL       = 'https://maria.ar/indice-respuestas-ia/solicitar';
const MAIL_FROM      = 'no-reply@maria.ar';

// --- helpers --------------------------------------------------------------
function salir(int $code, array $payload): never {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

function limpiar(string $s, int $max): string {
    return mb_substr(trim(preg_replace('/\s+/u', ' ', $s)), 0, $max);
}

function dir_cola(string $sub): string {
    $d = COLA_DIR . '/' . $sub;
    if (!is_dir($d)) { @mkdir($d, 0770, true); }
    return $d;
}

function contar_hoy(string $sub): int {
    $d = COLA_DIR . '/' . $sub;
    if (!is_dir($d)) return 0;
    $hoy = gmdate('Y-m-d');
    $n = 0;
    foreach (glob("$d/*.json") ?: [] as $f) {
        if (gmdate('Y-m-d', filemtime($f)) === $hoy) $n++;
    }
    return $n;
}

// --- método --------------------------------------------------------------
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST') {
    salir(405, ['ok' => false, 'error' => 'Usá el formulario.']);
}

// --- entrada -------------------------------------------------------------
$industria = limpiar((string)($_POST['industria'] ?? ''), 80);
$empresa   = limpiar((string)($_POST['empresa'] ?? ''), 120);
$dominio   = strtolower(limpiar((string)($_POST['dominio'] ?? ''), 120));
$email     = strtolower(limpiar((string)($_POST['email'] ?? ''), 160));

$dominio = preg_replace('#^https?://#', '', $dominio);
$dominio = preg_replace('#^www\.#', '', $dominio);
$dominio = explode('/', $dominio)[0];

// --- validación de forma ------------------------------------------------
if (!in_array(mb_strtolower($industria), array_map('mb_strtolower', INDUSTRIAS), true)) {
    salir(422, ['ok' => false, 'error' => 'Esa industria no está habilitada en la versión piloto.']);
}
if ($empresa === '') {
    salir(422, ['ok' => false, 'error' => 'Falta el nombre de la empresa.']);
}
if (!preg_match('/^[a-z0-9.-]+\.[a-z]{2,}$/', $dominio)) {
    salir(422, ['ok' => false, 'error' => 'El dominio no parece un dominio válido.']);
}
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    salir(422, ['ok' => false, 'error' => 'El email no es válido.']);
}

// --- límites de abuso y de gasto --------------------------------------
$ip = (string)($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');
$rateDir = dir_cola('_rate');
$rateFile = $rateDir . '/' . preg_replace('/[^0-9a-f:.]/i', '_', $ip) . '-' . gmdate('Y-m-d') . '.count';
$usos = is_file($rateFile) ? (int)file_get_contents($rateFile) : 0;
if ($usos >= TOPE_POR_IP) {
    salir(429, ['ok' => false, 'error' => 'Ya enviaste varios pedidos hoy desde esta conexión. Probá mañana.']);
}

$nuevasHoy = contar_hoy('pendientes_verificacion') + contar_hoy('pendientes')
           + contar_hoy('procesadas') + contar_hoy('rechazadas');
if ($nuevasHoy >= TOPE_GLOBAL) {
    salir(429, ['ok' => false, 'error' => 'Alcanzamos el tope de pedidos por hoy. Probá mañana.']);
}

// --- escribir el archivo de trabajo ---------------------------------
try {
    $id    = gmdate('Ymd\THis\Z') . '-' . bin2hex(random_bytes(3));
    $token = bin2hex(random_bytes(16));
} catch (Exception $e) {
    salir(500, ['ok' => false, 'error' => 'Error interno. Probá de nuevo.']);
}

$registro = [
    'id'          => $id,
    'industria'   => $industria,
    'empresa'     => $empresa,
    'dominio'     => $dominio,
    'email'       => $email,
    'ip'          => $ip,
    'creada_utc'  => gmdate('Y-m-d\TH:i:s+00:00'),
    'verificada_utc' => null,
    'estado'      => 'pendiente_verificacion',
    'token'       => $token,
    'motivo_rechazo' => null,
    'resultado'   => null,
];

$destino = dir_cola('pendientes_verificacion') . "/$id.json";
if (file_put_contents($destino, json_encode($registro, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE), LOCK_EX) === false) {
    salir(500, ['ok' => false, 'error' => 'No pudimos registrar el pedido. Probá más tarde.']);
}
file_put_contents($rateFile, (string)($usos + 1), LOCK_EX);

// --- email de verificación ------------------------------------------
$link = BASE_URL . '/confirmar.php?id=' . rawurlencode($id) . '&token=' . rawurlencode($token);
$cuerpo = "Hola,\n\n"
    . "Pediste el Índice de Visibilidad en Respuestas de IA para {$empresa} ({$dominio}).\n\n"
    . "Confirmá el pedido con este enlace:\n{$link}\n\n"
    . "Si no fuiste vos, ignorá este mensaje: sin confirmar, el pedido no se procesa.\n\n"
    . "— maria.ar\n";
$headers = "From: " . MAIL_FROM . "\r\nContent-Type: text/plain; charset=utf-8\r\n";
@mail($email, 'Confirmá tu pedido — Índice de Respuestas de IA', $cuerpo, $headers);

salir(200, [
    'ok' => true,
    'id' => $id,
    'mensaje' => 'Listo. Te mandamos un email a ' . $email . ': confirmá el pedido con el enlace y lo procesamos.',
]);
