import requests

from com.vmware import nsx_client
from com.vmware import nsx_policy_client
from vmware.vapi.bindings.stub import ApiClient
from vmware.vapi.bindings.stub import StubFactory
from vmware.vapi.lib import connect
from vmware.vapi.security.user_password import create_user_password_security_context
from vmware.vapi.stdlib.client.factories import StubConfigurationFactory
from com.vmware.nsx_policy.model_client import Segment
from com.vmware.nsx_policy.model_client import SegmentSubnet

# Create NSX client for a given endpoint (nsx_endpoint, nsx_policy_client)
def nsx_create_client(nsx_user='admin',
                      nsx_password='VMware1!VMware1!',
                      nsx_endpoint=nsx_policy_client,
                      nsx_host='nsx-mgr.corp.local', nsx_port=443):
    session = requests.session()
    session.verify = False
    requests.packages.urllib3.disable_warnings()

    connector = connect.get_requests_connector(
        session=session, msg_protocol='rest', url=f'https://{nsx_host}:{nsx_port}')
    stub_config = StubConfigurationFactory.new_runtime_configuration(
        connector, response_extractor=True)
    security_context = create_user_password_security_context(
        nsx_user, nsx_password)
    connector.set_security_context(security_context)

    stub_factory = nsx_endpoint.StubFactory(stub_config)

    return ApiClient(stub_factory)

# Create NSX Segment
def nsx_create_segment(nsx_client, segment_name, gateway_cidr, transport_zone_id='/infra/sites/default/enforcement-points/default/transport-zones/3a04c35c-5116-473e-af92-bc8dc7fab309', router_id='/infra/tier-0s/hol-gw'):
    subnet = SegmentSubnet(gateway_address=gateway_cidr)
    segment = Segment(transport_zone_path=transport_zone_id,
                      connectivity_path=router_id,
                      display_name=segment_name,
                      subnets=[subnet])
    nsx_client.infra.Segments.update(segment_name, segment)


def main(context=None, inputs={}):
    print('Connecting to NSX Manager...')
    client = nsx_create_client()

    if 'name' in inputs and 'gateway' in inputs:
        print(f"Creating Network segment {inputs['name']} - {inputs['gateway']}")
        nsx_create_segment(client, inputs['name'], inputs['gateway'])
    else:
        raise Exception(
            'No value for Segment name or Gateway. Segment not created')


if __name__ == "__main__":
    main()
