"""
Tier-2 test to verify the effect of osd_memory_target set at different precedence level
"""
import random

from ceph.ceph_admin import CephAdmin
from ceph.rados.core_workflows import RadosOrchestrator
from tests.rados.monitor_configurations import MonConfigMethods
from utility.log import Log

log = Log(__name__)


def run(ceph_cluster, **kw):
    """
    # CEPH-83580882
    # CEPH-83580881
    Test verifies the effect of osd_memory_target
     set at different precedence level
    Covers Customer BZ-2213873
    """
    log.info(run.__doc__)
    config = kw["config"]
    rhbuild = config.get("rhbuild")
    cephadm = CephAdmin(cluster=ceph_cluster, **config)
    rados_obj = RadosOrchestrator(node=cephadm)
    mon_obj = MonConfigMethods(rados_obj=rados_obj)
    osd_nodes = ceph_cluster.get_nodes(role="osd")

    def fetch_osd_config_value(_osd_id: str) -> tuple:
        get_omt = mon_obj.get_config(
            section=f"osd.{_osd_id}", param="osd_memory_target"
        )
        show_omt = mon_obj.show_config(
            daemon="osd", id=_osd_id, param="osd_memory_target"
        )
        return get_omt, show_omt

    log.info("Logging the original values of osd_memory_target for the cluster")
    out, _ = cephadm.shell(["ceph config dump | grep osd_memory_target"])
    log.info(out)

    if config.get("osd_level"):
        doc = """
        # CEPH-83580882
        This test is to verify precedence of osd_memory_target
        set at global OSD level and individual OSD level
        1. Create cluster with default configuration
        2. Verify the value of osd_memory_target set at OSD level
        3. Set the value of osd_memory_target at global osd level
        4. Pick a random OSD and set the osd_memory_target at individual OSD level
        5. Verify that the value set at individual OSD level took effect and overrode
        the global OSD value
        """
        log.info(doc)
        try:
            out, _ = cephadm.shell(args=["ceph osd ls"])
            osd_list = out.strip().split("\n")
            log.debug(f"List of OSDs: {osd_list}")

            # set a value for osd_memory_target at OSD level
            log.info("Setting a value for osd_memory_target at OSD level")
            assert mon_obj.set_config(
                section="osd", name="osd_memory_target", value="6000000000"
            )
            log.info("OSD config parameter osd_memory_target set successfully")

            osd_get_omt = mon_obj.get_config(section="osd", param="osd_memory_target")
            osd_show_omt = mon_obj.show_config(
                daemon="osd", id="0", param="osd_memory_target"
            )
            log.info(
                f"OSD osd_memory_target set at OSD level from ceph config get: {osd_get_omt}"
            )
            log.info(
                f"OSD osd_memory_target set at OSD level from ceph config show: {osd_show_omt}"
            )

            # pick an OSD at random to change the osd_memory_target at individual OSD level
            osd_id = random.choice(osd_list)
            log.debug(f"Chosen OSD: osd.{osd_id}")
            log.info(f"Setting a value for osd_memory_target at osd.{osd_id} level")
            assert mon_obj.set_config(
                section=f"osd.{osd_id}", name="osd_memory_target", value="5000000000"
            )
            log.info("OSD config parameter osd_memory_target set successfully")

            osdid_get_omt, osdid_show_omt = fetch_osd_config_value(osd_id)
            log.info(
                f"OSD osd_memory_target set for osd.{osd_id} from ceph config get: {osdid_get_omt}"
            )
            log.info(
                f"OSD osd_memory_target set for osd.{osd_id} from ceph config show: {osdid_show_omt}"
            )

            if not int(osdid_get_omt) == int(osdid_show_omt) == 5000000000:
                log.error(
                    f"Value of osd_memory_target for osd.{osd_id} not set as per expectation"
                )
                raise AssertionError(
                    f"Value of osd_memory_target for osd.{osd_id} not set as per expectation"
                )
            log.info(
                f"osd_memory_target parameter set at individual OSD level for osd.{osd_id} "
                f"has taken effect and verified successfully"
            )
        except AssertionError as AE:
            log.error(f"Execution failed with exception: {AE.__doc__}")
            log.exception(AE)
            return 1
        finally:
            log.info("\n ****** Executing finally block ******* \n")
            mon_obj.remove_config(section=f"osd.{osd_id}", name="osd_memory_target")
            mon_obj.remove_config(section="osd", name="osd_memory_target")
        return 0

    if config.get("host_level"):
        doc = """
        # CEPH-83580881
        # BZ-2213873
        This test is to verify the propagation of osd_memory_target parameter
        set at HOST level to individual OSDs
        1. Create cluster with default configuration
        2. Fetch a OSD node at random and list all the OSDs part of that host
        3. Pick a random OSD from the list obtained in previous step
        4. Change the osd_memory_target value for this OSD and verify the change
        5. Change the osd_memory_target at the host level and verify the change
        6. Ensure the value is propagated to OSDs by checking another random OSD's
        config param
        7. Ensure that the value osd_memory_target for the first OSD is unchanged
        as it has higher precedence
        8. Change the osd_memory_target value at osd level for the 2nd random OSD
        9. osd_memory_target value for the 2nd random OSD should get updated
        """
        log.info(doc)
        # Test will run for all releases once BZ-2213873 has been back-ported
        if not rhbuild.startswith("6"):
            log.info(
                "\n \n ********\n [29-Nov-2023] "
                "Test is currently only valid for RHCS 6.1z3 Quincy build 160 and above"
                f"\n Input RHCS build - {rhbuild}, passing the test without running"
                f"\n *********"
            )
            return 0
        try:
            osd_node = random.choice(osd_nodes)
            log.info(f"Random OSD host chosen for the test : {osd_node.hostname}")

            osd_list = rados_obj.collect_osd_daemon_ids(osd_node=osd_node)
            log.info(f"List of OSDs part of {osd_node.hostname} : {osd_list}")

            osd_ran = random.choice(osd_list)
            osd_list.remove(osd_ran)
            log.info(f"OSD chosen at random : {osd_ran}")
            # fetch the original value of osd_memory_target for the chosen OSD before start of test
            osd_ran_get_omt, osd_ran_show_omt = fetch_osd_config_value(osd_ran)
            log.info(
                f"OSD {osd_ran} osd_memory_target out from ceph config get: {osd_ran_get_omt}"
            )
            log.info(
                f"OSD {osd_ran} osd_memory_target out from ceph config show: {osd_ran_show_omt}"
            )
            # set a custom value of osd_memory_target for the OSD
            log.info(f"Setting a value for osd_memory_target at osd.{osd_ran} level")
            assert mon_obj.set_config(
                section=f"osd.{osd_ran}", name="osd_memory_target", value="4500000000"
            )
            log.info("OSD config parameter osd_memory_target set successfully")

            osdran_get_omt, osdran_show_omt = fetch_osd_config_value(osd_ran)
            log.info(
                f"OSD osd_memory_target set for osd.{osd_ran} from ceph config get: {osdran_get_omt}"
            )
            log.info(
                f"OSD osd_memory_target set for osd.{osd_ran} from ceph config show: {osdran_show_omt}"
            )
            if not int(osdran_get_omt) == int(osdran_show_omt) == 4500000000:
                log.error(
                    f"Value of osd_memory_target for osd.{osd_ran} not set as per expectation"
                )
                raise AssertionError(
                    f"Value of osd_memory_target for osd.{osd_ran} not set as per expectation"
                )
            log.info(
                f"osd_memory_target parameter set at individual OSD level for osd.{osd_ran}"
                f"has taken effect and verified successfully"
            )

            # set the osd_memory_target value at host level
            log.info("Setting a value for osd_memory_target at Host level")
            assert mon_obj.set_config(
                section="osd",
                location_type="host",
                location_value=osd_node.hostname,
                name="osd_memory_target",
                value="5500000000",
            )
            log.info(
                f"osd_memory_target for host: {osd_node.hostname} set successfully"
            )
            # fetch another osd and check if osd_memory_target is same as the value set at host level
            osd_ran2 = random.choice(osd_list)
            log.info(f"Another OSD chosen at random : {osd_ran2}")

            osdran2_get_omt, osdran2_show_omt = fetch_osd_config_value(osd_ran2)
            log.info(
                f"OSD osd_memory_target set for osd.{osd_ran2} from ceph config get: {osdran2_get_omt}"
            )
            log.info(
                f"OSD osd_memory_target set for osd.{osd_ran2} from ceph config show: {osdran2_show_omt}"
            )

            if not int(osdran2_get_omt) == int(osdran2_show_omt) == 5500000000:
                log.error(
                    f"Value of osd_memory_target for osd.{osd_ran2} is not same as host"
                )
                raise AssertionError(
                    f"Value of osd_memory_target for osd.{osd_ran2} is not same as host"
                )
            log.info(
                f"Value of osd_memory_target for osd.{osd_ran2} is same as Host: 5500000000"
            )
            # check the value osd_memory_target of first random osd, should be unchanged
            osd_ran_get_omt, osd_ran_show_omt = fetch_osd_config_value(osd_ran)
            log.info(
                f"OSD.{osd_ran} osd_memory_target from ceph config get: {osd_ran_get_omt}"
            )
            log.info(
                f"OSD.{osd_ran} osd_memory_target from ceph config show: {osd_ran_show_omt}"
            )
            assert int(osdran_get_omt) == int(osdran_show_omt) == 4500000000
            log.info(
                f"Value of osd_memory_target for osd.{osd_ran} is unchanged as expected."
            )

            # Changing the value of osd_memory_target for the second random OSD
            log.info(f"Setting a value for osd_memory_target at osd.{osd_ran2} level")
            assert mon_obj.set_config(
                section=f"osd.{osd_ran2}", name="osd_memory_target", value="5800000000"
            )
            log.info("OSD config parameter osd_memory_target set successfully")

            # check the value osd_memory_target of 2nd random osd, should now be 5800000000
            osdran2_get_omt, osdran2_show_omt = fetch_osd_config_value(osd_ran2)
            log.info(
                f"OSD osd_memory_target set for osd.{osd_ran2} from ceph config get: {osdran2_get_omt}"
            )
            log.info(
                f"OSD osd_memory_target set for osd.{osd_ran2} from ceph config show: {osdran2_show_omt}"
            )
            if not int(osdran2_get_omt) == int(osdran2_show_omt) == 5800000000:
                log.error(
                    f"Value of osd_memory_target for osd.{osd_ran2} not set as per expectation"
                )
                raise AssertionError(
                    f"Value of osd_memory_target for osd.{osd_ran2} not set as per expectation"
                )
            log.info(
                f"value of osd_memory_target for osd.{osd_ran2} changed "
                f"from host value of 5500000000 to 5800000000 as per expectation"
            )
            log.info(
                "Test successfully verifies the propagation of osd_memory_target"
                " set at host level to OSDs and precedence of value set at individual"
                " daemon level overriding the value set at host level"
            )
        except AssertionError as AE:
            log.error(f"Execution failed with exception: {AE.__doc__}")
            log.exception(AE)
            return 1
        finally:
            log.info("\n ****** Executing finally block ******* \n")
            mon_obj.remove_config(section=f"osd.{osd_ran}", name="osd_memory_target")
            mon_obj.remove_config(section=f"osd.{osd_ran2}", name="osd_memory_target")
            mon_obj.remove_config(
                section="osd",
                location_type="host",
                location_value=osd_node.hostname,
                name="osd_memory_target",
            )
            mon_obj.remove_config(section="osd", name="osd_memory_target")
        log.info("All verifications completed")
        return 0
