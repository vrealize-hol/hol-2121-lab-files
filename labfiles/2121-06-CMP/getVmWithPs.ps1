# Connect to vCenter
Set-PowerCLIConfiguration -InvalidCertificateAction Ignore -Confirm:$false
Connect-VIserver "vcsa-01a.corp.local" -username "administrator@regiona.local" -password "VMware1!" -ErrorAction Stop

# Search for the VM by name
$vmPartialName = $inputs.vmName
Write-Host "Searching VM with name matching $vmPartialName"
$matchingVms = Get-VM | Where-Object { $_.Name -like "*$vmPartialName*" }
Write-Host "$($matchingVms.Count) VM(s) found with name matching $vmPartialName"

return $matchingVms[0].Name