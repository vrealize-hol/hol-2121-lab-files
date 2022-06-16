provider "vra" {
    url           = var.url
    refresh_token = var.refresh_token
    insecure      = var.insecure
}

data "vra_project" "this" {
  name = ""
}

resource "vra_blueprint" "this" {
  name        = ""
  description = "Created by vRA terraform provider"

  project_id = data.vra_project.this.id

 content = <<-EOT
    formatVersion: 1
    inputs:
      image:
        type: string
        description: "Image"
      flavor:
        type: string
        description: "Flavor"
    resources:
      WebServer:
        type: Cloud.Machine
        properties:
          image: $${input.image}
          flavor: $${input.flavor}
          constraints:
            - tag: 'cloud:vsphere'
          networks:
            - network: '$${resource.Cloud_Network.id}'
              assignment: static
      Cloud_Network:
        type: Cloud.Network
        properties:
          networkType: existing
        constraints:
         - tag: 'net:vsphere'
  EOT
}

resource "vra_blueprint_version" "this" {
  blueprint_id = vra_blueprint.this.id
  description  = "Version by vRA terraform provider"
  version      = 
  release      = false
  change_log   = ""
}