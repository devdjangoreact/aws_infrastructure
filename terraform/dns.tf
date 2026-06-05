# Site A-records ONLY. This file MUST NOT manage MX, TXT (SPF/DKIM/DMARC), mail CNAME/SRV,
# or any other pre-existing record. Mail and non-site records stay under manual control in
# Cloudflare. Never import a whole zone or use a zone-wide ownership resource here.
resource "cloudflare_dns_record" "site" {
  for_each = local.services

  zone_id = data.cloudflare_zone.site[each.key].zone_id
  name    = each.key
  type    = "A"
  content = aws_eip.web.public_ip
  proxied = false
  ttl     = 60
  comment = "Managed by Terraform (${local.project}) - site A-record only"
}
