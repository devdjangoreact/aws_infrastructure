#requires -Version 5.1
<#
.SYNOPSIS
  One-time DNS cutover preflight: deletes existing apex A-records for the 6 managed domains so
  Terraform can create fresh DNS-only A-records pointing at the EC2 Elastic IP.

.DESCRIPTION
  Deletes ONLY type=A records at the zone apex (name == domain). It never touches MX, TXT, CNAME,
  SRV, or any other record, so mail (including the iCloud MX on buyraq.com) is left intact.

  Requires the Cloudflare API token in the CLOUDFLARE_API_TOKEN environment variable
  (Zone:Read + DNS:Edit on the managed zones).

.PARAMETER DryRun
  List the apex A-records that WOULD be deleted, without deleting anything.

.EXAMPLE
  $env:CLOUDFLARE_API_TOKEN = '...'; ./scripts/preflight-dns.ps1 -DryRun
  $env:CLOUDFLARE_API_TOKEN = '...'; ./scripts/preflight-dns.ps1
#>
[CmdletBinding()]
param(
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$domains = @(
  'buyraq.com',
  'codehelp.pp.ua',
  'cosmeticpro.pp.ua',
  'ddnsteltonicka.pp.ua',
  'solovkadmytro.pp.ua',
  'solovkaskincare.pp.ua'
)

$token = $env:CLOUDFLARE_API_TOKEN
if ([string]::IsNullOrWhiteSpace($token)) {
  Write-Error 'CLOUDFLARE_API_TOKEN is not set in the environment.'
  exit 2
}

$headers = @{
  Authorization = "Bearer $token"
  'Content-Type' = 'application/json'
}
$api = 'https://api.cloudflare.com/client/v4'

foreach ($domain in $domains) {
  Write-Host "=== $domain ===" -ForegroundColor Cyan

  $zoneResp = Invoke-RestMethod -Method Get -Headers $headers -Uri "$api/zones?name=$domain"
  if (-not $zoneResp.success -or $zoneResp.result.Count -eq 0) {
    Write-Warning "  zone not found in this Cloudflare account; skipping"
    continue
  }
  $zoneId = $zoneResp.result[0].id

  # Apex A-records only: type=A AND name exactly equals the domain.
  $recResp = Invoke-RestMethod -Method Get -Headers $headers -Uri "$api/zones/$zoneId/dns_records?type=A&name=$domain"
  $apexA = $recResp.result | Where-Object { $_.type -eq 'A' -and $_.name -eq $domain }

  if (-not $apexA -or $apexA.Count -eq 0) {
    Write-Host "  no apex A-record; nothing to do"
    continue
  }

  foreach ($rec in $apexA) {
    if ($DryRun) {
      Write-Host "  [dry-run] would delete A $($rec.name) -> $($rec.content) (proxied=$($rec.proxied), id=$($rec.id))" -ForegroundColor Yellow
    }
    else {
      $del = Invoke-RestMethod -Method Delete -Headers $headers -Uri "$api/zones/$zoneId/dns_records/$($rec.id)"
      if ($del.success) {
        Write-Host "  deleted A $($rec.name) -> $($rec.content) (id=$($rec.id))" -ForegroundColor Green
      }
      else {
        Write-Warning "  failed to delete record id=$($rec.id)"
      }
    }
  }
}

Write-Host ""
if ($DryRun) {
  Write-Host "Dry-run complete. Re-run without -DryRun to delete, then run terraform apply." -ForegroundColor Cyan
}
else {
  Write-Host "Preflight complete. Now run terraform apply to create DNS-only A-records." -ForegroundColor Cyan
}
