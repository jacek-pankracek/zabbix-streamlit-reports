<?php
// Forward cookie to Zabbix API
$cookie = $_SERVER['HTTP_COOKIE'] ?? '';

$ch = curl_init('http://127.0.0.1/api_jsonrpc.php');
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    "Cookie: $cookie"
]);

// Minimal request: get current user with groups
$data = [
    'jsonrpc' => '2.0',
    'method' => 'user.get',
    'params' => [
        'output' => ['userid'],
        'selectUsrgrps' => ['name']
    ],
    'id' => 1
];
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));

$response = json_decode(curl_exec($ch), true);
curl_close($ch);

if (isset($response['result'][0]['usrgrps'])) {
    foreach ($response['result'][0]['usrgrps'] as $grp) {
        if (strcasecmp($grp['name'], 'reports') === 0) {
            http_response_code(200);
            exit;
        }
    }
}

http_response_code(401);
exit;