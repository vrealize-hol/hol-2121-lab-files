provider "vra" {
    url           = var.url
    refresh_token = var.refresh_token
    insecure      = var.insecure
}

data "vra_zone" "vsphere" {
  name = var.vsphere_zone_name
}

resource "vra_project" "this" {
  name        = ""
  description =  "Terraform created project"

  zone_assignments {
    zone_id          = data.vra_zone.vsphere.id
    priority         = 
    max_instances    = 
    cpu_limit        =
    memory_limit_mb  =
    storage_limit_gb =
  }

  shared_resources = true

  administrators = 
  members =
}

