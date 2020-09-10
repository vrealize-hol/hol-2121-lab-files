# test PS calling Python
cls

$path = Get-Location
$cmd = 'python $path\template.py -q 1.1.1.3'
Try {
    $output = Invoke-Expression -Command $cmd -ErrorVariable errorVar
}
Catch {
    Write-Output "Error while running the Python validation: $errorVar"
}

if ($output -clike 'PASS*') {
    $result = $true
} elseif ($output -clike 'FAIL*') {
    $result = $false
} elseif ($output -clike 'ERROR*') {
    Write-Output "There was an ERROR returned by the Python script"
} else {
    Write-Output "result = neither PASS nor FAIL nor ERROR"
}

Write-Output $output  # This will write everything passed back through the pipeline from the Python script

