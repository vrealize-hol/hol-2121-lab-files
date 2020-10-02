provider "vra" {
  url           = var.url
  refresh_token = var.refresh_token
  insecure      = var.insecure
}

data "vra_project" "this" {
  name = ""
}

data "vra_blueprint" "this" {
  name = ""
}

resource "vra_blueprint_version" "this" {
  blueprint_id = data.vra_blueprint.this.id
  description  = "Released from vRA terraform provider"
  version      = 
  release      = true
  change_log   = ""
}

resource "vra_catalog_source_blueprint" "this" {
  depends_on = [vra_blueprint_version.this]
  name       = ""
  project_id = data.vra_project.this.id
}

resource "vra_catalog_source_entitlement" "this" {
  depends_on        = [vra_catalog_source_blueprint.this]
  catalog_source_id = vra_catalog_source_blueprint.this.id
  project_id        = data.vra_project.this.id
}