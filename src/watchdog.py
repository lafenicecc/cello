import time
import logging

from threading import Thread

from modules import host_handler, cluster_handler
from common import LOG_LEVEL, log_handler, SYS_DELETER, SYS_USER

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)


def chain_check_health(chain_id, retries=3, period=5):
    """
    Check the chain health.

    :param chain_id: id of the chain
    :param retries: how many retries before thinking not health
    :param period: wait between two retries
    :return:
    """
    # if not cluster_handler.check_health(chain_id) \
    #        and c['user_id'] != SYS_UNHEALTHY:
    #    cluster_handler.release_cluster(c['id'], record=False)
    logger.debug("Chain {}: checking health".format(chain_id))
    chain = cluster_handler.get_by_id(chain_id)
    if not chain:
        logger.warn("Not find chain with id = {}".format(chain_id))
        return
    chain_user_id = chain.get("user_id")

    # we should never operate on in-processing chains unless deleting one
    if chain_user_id.startswith(SYS_USER):
        if chain_user_id.startswith(SYS_DELETER):  # in system processing, TBD
            for i in range(retries):
                time.sleep(period)
                if cluster_handler.get_by_id(chain_id).get("user_id") != \
                        chain_user_id:
                    return
            logger.info("Delete in-deleting chain {}".format(chain_id))
            cluster_handler.delete(chain_id)
        return

    # free or used by user, then check its health
    for i in range(retries):
        if cluster_handler.refresh_health(chain_id):  # chain is healthy
            return
        else:
            time.sleep(period)
    logger.warn("Chain {} is unhealthy!".format(chain_id))
    # only reset free chains
    if cluster_handler.get_by_id(chain_id).get("user_id") == "":
        logger.info("Deleting free unhealthy chain {}".format(chain_id))
        # cluster_handler.delete(chain_id)
        cluster_handler.reset_free_one(chain_id)


def host_check_chains(host_id):
    """
    Check the chain health on the host.

    :param host_id:
    :return:
    """
    logger.debug("Host {}: checking cluster health".format(host_id))
    clusters = cluster_handler.list(filter_data={"host_id": host_id})
    for c in clusters:  # concurrent health check is safe for multi-chains
        t = Thread(target=chain_check_health, args=(c.get("id"),))
        t.start()
        t.join(timeout=15)


def host_check_fillup(host_id):
    """
    Check one host.

    :param host_id:
    :return:
    """
    logger.debug("Host {}: checking fillup".format(host_id))
    host = host_handler.get_by_id(host_id)
    if host.get("autofill") == "true":
        host_handler.fillup(host_id)


def host_check(host_id, retries=3, period=3):
    """
    Run check on specific host.
    Check status and check each chain's health.

    :param host_id: id of the checked host
    :param retries: how many retries before thnking it's inactive
    :param period: retry wait
    :return:
    """
    for _ in range(retries):
        if host_handler.refresh_status(host_id):  # host is active
            logger.debug("host {} is active, check its chains".format(host_id))
            host_check_chains(host_id)
            time.sleep(period)
            host_check_fillup(host_id)
            break
        time.sleep(period)


def watch_run(period=15):
    """
    Run the checking in period.

    :param period: Wait period between two checking
    :return:
    """
    while True:
        logger.info("Watchdog run checks with period = %d s", period)
        hosts = list(host_handler.list())
        for h in hosts:  # operating on different host is safe
            t = Thread(target=host_check, args=(h.get("id"),))
            t.start()
            t.join(timeout=period)
        time.sleep(period)


if __name__ == '__main__':
    watch_run()
