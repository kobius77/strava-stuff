<?php
// Set your Strava app credentials from environment variables
$client_id = getenv('STRAVA_CLIENT_ID');
$client_secret = getenv('STRAVA_CLIENT_SECRET');

// Check if the 'code' parameter exists in the query string
if (isset($_GET['code'])) {
    $authorization_code = $_GET['code'];

    // Step 1: Exchange the authorization code for an access token
    $url = 'https://www.strava.com/api/v3/oauth/token';
    
    // Prepare the POST data
    $post_data = [
        'client_id' => $client_id,
        'client_secret' => $client_secret,
        'code' => $authorization_code,
        'grant_type' => 'authorization_code'
    ];
    
    // Set up the cURL request
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($post_data));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    
    // Execute the request and get the response
    $response = curl_exec($ch);
    curl_close($ch);

    // Step 2: Parse the response and display the access token
    $data = json_decode($response, true);

    if (isset($data['access_token'])) {
        echo "<h1>Authorization Successful!</h1>";
        echo "<p>Access Token: " . htmlspecialchars($data['access_token']) . "</p>";
        echo "<p>Refresh Token: " . htmlspecialchars($data['refresh_token']) . "</p>";
    } else {
        echo "<h1>Error</h1>";
        echo "<p>Failed to retrieve access token. Response: " . htmlspecialchars($response) . "</p>";
    }
} else {
    echo "<h1>Error</h1>";
    echo "<p>No authorization code found in the URL. Make sure you granted permission.</p>";
}
?>
