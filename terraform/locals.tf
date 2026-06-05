locals {
  # Managed domain => service_name (1:1). Used for DNS records and tagging.
  services = {
    "buyraq.com"            = "buyraq"
    "codehelp.pp.ua"        = "codehelp"
    "cosmeticpro.pp.ua"     = "cosmeticpro"
    "ddnsteltonicka.pp.ua"  = "ddnsteltonicka"
    "solovkadmytro.pp.ua"   = "solovkadmytro"
    "solovkaskincare.pp.ua" = "solovkaskincare"
  }

  project = "static-sites-infra"
}
