import __future__

import datetime
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import get_project, db, log_handler, get_project, \
    clean_exited_containers, check_daemon_url

from common.utils import CLUSTER_API_PORT_START

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(log_handler)


class ClusterHandler(object):
    def __init__(self):
        self.collections = db["cluster"]
        self.collections_released = db["cluster_released"]

    def _start_compose_project(self, name, port, daemon_url):
        logger.info("start compose project")
        os.environ['DOCKER_HOST'] = daemon_url
        os.environ['COMPOSE_PROJECT_NAME'] = name
        os.environ['PEER_NETWORKID'] = name
        os.environ['API_URL_PORT'] = port
        project = get_project("./common")
        logger.warn(project.up(detached=True))

    def _stop_compose_project(self, name, port, daemon_url):
        logger.info("stop compose project")
        os.environ['DOCKER_HOST'] = daemon_url
        os.environ['COMPOSE_PROJECT_NAME'] = name
        os.environ['PEER_NETWORKID'] = name
        os.environ['API_URL_PORT'] = port
        project = get_project("./common")
        project.stop()
        project.remove_stopped()

    def _clean_containers(self, daemon_url):
        logger.info("clean exited containers")
        clean_exited_containers(daemon_url)

    def list(self):
        logger.info("list all clusters")
        result = map(self._serialize, self.collections.find())
        return result

    def get(self, id):
        logger.info("get a cluster")
        return self.collections.find_one({"id": id})

    def create(self, name, daemon_url, api_url="", user_id=""):
        """ create a cluster based on given data
        TODO: maybe need other id generation mechanism
        TODO: maybe need to check daemon_url status

        :return bool
        """
        logger.info("create a cluster")
        if not daemon_url.startswith("tcp://"):
            daemon_url = "tcp://" + daemon_url
        if not check_daemon_url(daemon_url):
            logger.warn("daemon_url is not valid:"+daemon_url)
            return False
        if not api_url:  # automatically schedule one
            api_url = self._gen_api_url(daemon_url)
        c = {
                'name': name,
                'user_id': user_id,
                'api_url': api_url,
                'daemon_url': daemon_url,
                'create_ts': datetime.datetime.utcnow(),
                'release_ts': "",
            }
        ins_id = self.collections.insert_one(c).inserted_id
        self.collections.update({"_id": ins_id}, {"$set": {"id": str(ins_id)}})
        try:
            self._start_compose_project(name=str(ins_id),
                                        port=api_url.split(":")[-1],
                                        daemon_url=daemon_url)
        except Exception as e:
            logger.warn(e)
            return False
        return True

    def delete(self, id, record=False):
        """ Delete a cluster instance
        :param record: Whether to record into the released collections
        """
        logger.info("delete a cluster with id="+id)
        ins = self.collections.find_one({"id": id})
        if not ins:
            logger.warn("Cannot delete non-existed instance")
            return False
        api_url = ins.get("api_url", "")
        daemon_url = ins.get("daemon_url", "")
        try:
            self._stop_compose_project(name=id,
                                   port=api_url.split(":")[-1],
                                   daemon_url=daemon_url)
            self._clean_containers(daemon_url)
        except Exception as e:
            logger.warn(e)
            return False
        if record:
            ins["release_ts"] = datetime.datetime.utcnow()
            logger.info("Record the cluster info into released collection")
            self.collections_released.insert_one(ins)
        self.collections.delete_one({"id": id})
        return True

    def apply_cluster(self, user_id):
        """ Apply a cluster for a user
        """
        result = self.collections.find_one({"user_id": user_id})
        if result:  # already have one
            logger.info("Already have one for"+user_id)
            logger.info(self._serialize(result))
            return self._serialize(result)
        free_one = self.collections.find_one({"user_id": ""})
        if not free_one:
            logger.info("Not find free one for"+user_id)
            return {}
        else:
            free_one['apply_ts'] = datetime.datetime.utcnow(),
            logger.info("Assign free one for"+user_id)
            logger.info(self._serialize(free_one))
            return self._serialize(free_one)

    def release_cluster(self, user_id):
        """ Release a cluster for a user_id and recreate it.
        """
        result = self.collections.find_one({"user_id": user_id})
        if not result:  # not have one
            logger.warn("There is no cluster for"+user_id)
            return False
        cluster_id = result.get("id", "")
        cluster_name = result.get("name", "")
        cluster_daemon_url = result.get("daemon_url", "")
        cluster_api_url = result.get("api_url", "")
        if not self.delete(cluster_id, record=True):
            logger.warn("Delete cluster error with id="+cluster_id)
            return False
        if not self.create(cluster_name, cluster_daemon_url, cluster_api_url):
            logger.warn("Create cluster error with name="+cluster_name)
            return False

    def set_user_id(self, doc, user_id):
        """
        Set the user_id value to given doc
        """
        return self.collections.update({"id": doc.get('id','')},
                                       {"$set": {"user_id": user_id}})

    def _serialize(self, doc):
        return {
            'id': doc.get('id', ''),
            'name': doc.get('name', ''),
            'user_id': doc.get('user_id', ''),
            'api_url': doc.get('api_url', ''),
            'daemon_url': doc.get('daemon_url', ''),
            'create_ts': doc.get('create_ts', ''),
            'apply_ts': doc.get('apply_ts', ''),
            'release_ts': doc.get('release_ts', ''),
        }

    def _gen_api_url(self, daemon_url):
        """ Generate an api url automatically.
        :param daemon_url, may look like: tcp://192.168.0.1:2375
        :param d
        """
        logger.info("gen_api_url, daemon_url="+daemon_url)
        segs = daemon_url.split(":")
        if len(segs) != 3:
            logger.error("invalid daemon url = ", daemon_url)
            return ""
        host_ip = segs[1][2:]
        logger.debug("host_ip="+host_ip)
        exists = self.collections.find({"daemon_url": daemon_url})
        api_url_existed = list(map(lambda c: c.get("api_url", ""),
                                   exists))
        logger.warn("api_url_existed:")
        logger.warn(api_url_existed)
        for i in range(len(list(api_url_existed))+1):
            new_url = "http://{0}:{1}".format(host_ip, CLUSTER_API_PORT_START+i)
            logger.debug("try new_url="+new_url)
            if new_url not in api_url_existed:
                logger.debug("get valid new_url="+new_url)
                return new_url
        logger.warn("no valid api_url is generated")
        return ""

cluster_handler = ClusterHandler()