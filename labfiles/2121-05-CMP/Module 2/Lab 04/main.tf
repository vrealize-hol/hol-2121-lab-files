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

data "vra_catalog_item" "this" {
  name            = data.vra_blueprint.this.name
  expand_versions = true
}

resource "vra_deployment" "this" {
  name        = ""
  description = "terraform test deployment"

  catalog_item_id      = data.vra_catalog_item.this.id
  catalog_item_version = 2
  project_id           = data.vra_project.this.id

  inputs = {
    flavor = ""
    image  = ""
  }

  timeouts {
    create = "30m"
    delete = "30m"
    update = "30m"
  }
}