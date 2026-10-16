"""PET environment constants."""

PET_RT_ADMIN = "PET_RT_ADMIN"
KUBECTL = "/usr/bin/kubectl"

TCK8S_NAMESPACE = "tks-in02-pet1-tc"
TCMS_NAMESPACE = "tc-product-k8s-tks-in02-pet1"

TCK8S_HELM_DIR = "${HOME}/helm-charts"

TCK8S_HELM_GUIDELINES = (
    f"Helm charts for TCK8S live on PET_RT_ADMIN at {TCK8S_HELM_DIR}. "
    "Layout: helm-charts/global — global values (charts, configs, krb5, certificates); "
    "helm-charts/deployments — TCK8S deployments; "
    "helm-charts/services — TCK8S service configurations."
)

TCMS_PODS_GUIDELINES = (
    "All TCMS pods are microservices."
)

DAEMON_CONFIG_PATH = "/users/tksapp1/var/tks/config/.Op9DmnMonitor.cfg"

WL_DOMAIN_HOME = "${HOME}/JEE/ABPProduct/WLS/ABP-FULL"
WL_SCRIPTS_DIR = "${HOME}/JEE/ABPProduct/scripts/ABP-FULL"
WL_SERVER_CACHE_DIR = "${HOME}/JEE/ABPProduct/WLS/ABP-FULL/servers/ABPServer"
WL_LOG_DIR = "${HOME}/JEE/ABPProduct/logs/ABP-FULL/ABPServer"
WL_PROPERTIES_DIR = "${HOME}/JEE/ABPProduct/config_files/ABP-FULL/ABPServer"

CM_WL_PROPERTIES_GUIDELINES = (
    "Application properties are under ${HOME}/JEE/ABPProduct/config_files/ABP-FULL/ABPServer. "
    "When updating property files: (a) present proposed changes per file and obtain explicit user "
    "approval before calling apply; (b) on apply, a timestamped backup is created — report backup "
    "paths prominently to the user; (c) only then are changes written to the file."
)

CM_TYPE_SUFFIX = {
    "prepaid": "Server_CM_Prepaid",
    "postpaid": "Server_CM_Postpaid",
    "internal_api": "Server_CM_Internal_API",
    "collection_scanner": "Server_Collection_Scanner",
    "webservices": "Server_CM_WebServices",
    "lock_server": "Server_LockServer",
    "srm": "Server_SRM",
}

# PET CM WebLogic instances: machine_name -> user@host (from unix-server config).
# Each entry: machine_name, user, host, cm_type.
CM_WL_INSTANCES = [
    # Prepaid — tcslocwleapp1..4
    {"machine_name": "CM31-Server_CM_Prepaid", "user": "ptcmwl11", "host": "tcslocwleapp1", "cm_type": "prepaid"},
    {"machine_name": "CM32-Server_CM_Prepaid", "user": "ptcmwl12", "host": "tcslocwleapp1", "cm_type": "prepaid"},
    {"machine_name": "CM33-Server_CM_Prepaid", "user": "ptcmwl13", "host": "tcslocwleapp1", "cm_type": "prepaid"},
    {"machine_name": "CM41-Server_CM_Prepaid", "user": "ptcmwl21", "host": "tcslocwleapp2", "cm_type": "prepaid"},
    {"machine_name": "CM42-Server_CM_Prepaid", "user": "ptcmwl22", "host": "tcslocwleapp2", "cm_type": "prepaid"},
    {"machine_name": "CM43-Server_CM_Prepaid", "user": "ptcmwl23", "host": "tcslocwleapp2", "cm_type": "prepaid"},
    {"machine_name": "CM51-Server_CM_Prepaid", "user": "ptcmwl31", "host": "tcslocwleapp3", "cm_type": "prepaid"},
    {"machine_name": "CM52-Server_CM_Prepaid", "user": "ptcmwl32", "host": "tcslocwleapp3", "cm_type": "prepaid"},
    {"machine_name": "CM53-Server_CM_Prepaid", "user": "ptcmwl33", "host": "tcslocwleapp3", "cm_type": "prepaid"},
    {"machine_name": "CM61-Server_CM_Prepaid", "user": "ptcmwl41", "host": "tcslocwleapp4", "cm_type": "prepaid"},
    {"machine_name": "CM62-Server_CM_Prepaid", "user": "ptcmwl42", "host": "tcslocwleapp4", "cm_type": "prepaid"},
    {"machine_name": "CM63-Server_CM_Prepaid", "user": "ptcmwl43", "host": "tcslocwleapp4", "cm_type": "prepaid"},
    # Internal API — tcslocwleapp5..6
    {"machine_name": "CM71-Server_CM_Internal_API", "user": "ptcmwl51", "host": "tcslocwleapp5", "cm_type": "internal_api"},
    {"machine_name": "CM72-Server_CM_Internal_API", "user": "ptcmwl52", "host": "tcslocwleapp5", "cm_type": "internal_api"},
    {"machine_name": "CM73-Server_CM_Internal_API", "user": "ptcmwl53", "host": "tcslocwleapp5", "cm_type": "internal_api"},
    {"machine_name": "CM81-Server_CM_Internal_API", "user": "ptcmwl61", "host": "tcslocwleapp6", "cm_type": "internal_api"},
    {"machine_name": "CM82-Server_CM_Internal_API", "user": "ptcmwl62", "host": "tcslocwleapp6", "cm_type": "internal_api"},
    {"machine_name": "CM83-Server_CM_Internal_API", "user": "ptcmwl63", "host": "tcslocwleapp6", "cm_type": "internal_api"},
    # WebServices — tcslocwleapp7..8
    {"machine_name": "CM91-Server_CM_WebServices", "user": "ptcmwl71", "host": "tcslocwleapp7", "cm_type": "webservices"},
    {"machine_name": "CM92-Server_CM_WebServices", "user": "ptcmwl72", "host": "tcslocwleapp7", "cm_type": "webservices"},
    {"machine_name": "CM93-Server_CM_WebServices", "user": "ptcmwl73", "host": "tcslocwleapp7", "cm_type": "webservices"},
    {"machine_name": "CM101-Server_CM_WebServices", "user": "ptcmwl81", "host": "tcslocwleapp8", "cm_type": "webservices"},
    {"machine_name": "CM102-Server_CM_WebServices", "user": "ptcmwl82", "host": "tcslocwleapp8", "cm_type": "webservices"},
    {"machine_name": "CM103-Server_CM_WebServices", "user": "ptcmwl83", "host": "tcslocwleapp8", "cm_type": "webservices"},
    # Lock / Collection / SRM — tcslocwleapp9..11
    {"machine_name": "CM111-Server_LockServer", "user": "ptcmwl91", "host": "tcslocwleapp9", "cm_type": "lock_server"},
    {"machine_name": "CM112-Server_Collection_Scanner", "user": "ptcmwl92", "host": "tcslocwleapp9", "cm_type": "collection_scanner"},
    {"machine_name": "CM113-Server_SRM", "user": "ptcmwl93", "host": "tcslocwleapp9", "cm_type": "srm"},
    {"machine_name": "CM121-Server_LockServer", "user": "ptcmwl101", "host": "tcslocwleapp10", "cm_type": "lock_server"},
    {"machine_name": "CM122-Server_Collection_Scanner", "user": "ptcmwl102", "host": "tcslocwleapp10", "cm_type": "collection_scanner"},
    {"machine_name": "CM123-Server_SRM", "user": "ptcmwl103", "host": "tcslocwleapp10", "cm_type": "srm"},
    {"machine_name": "CM131-Server_SRM", "user": "ptcmwl111", "host": "tcslocwleapp11", "cm_type": "srm"},
    {"machine_name": "CM132-Server_SRM", "user": "ptcmwl112", "host": "tcslocwleapp11", "cm_type": "srm"},
    {"machine_name": "CM133-Server_SRM", "user": "ptcmwl113", "host": "tcslocwleapp11", "cm_type": "srm"},
    # Postpaid — tcsloswleapp* / tcsloawleapp*
    {"machine_name": "CM141-Server_CM_Postpaid", "user": "ptsrwl11", "host": "tcsloswleapp1", "cm_type": "postpaid"},
    {"machine_name": "CM142-Server_CM_Postpaid", "user": "ptsrwl12", "host": "tcsloswleapp1", "cm_type": "postpaid"},
    {"machine_name": "CM143-Server_CM_Postpaid", "user": "ptsrwl13", "host": "tcsloswleapp1", "cm_type": "postpaid"},
    {"machine_name": "CM151-Server_CM_Postpaid", "user": "ptsrwl21", "host": "tcsloswleapp2", "cm_type": "postpaid"},
    {"machine_name": "CM152-Server_CM_Postpaid", "user": "ptsrwl22", "host": "tcsloswleapp2", "cm_type": "postpaid"},
    {"machine_name": "CM153-Server_CM_Postpaid", "user": "ptsrwl23", "host": "tcsloswleapp2", "cm_type": "postpaid"},
    {"machine_name": "CM161-Server_CM_Postpaid", "user": "ptadwl11", "host": "tcsloawleapp1", "cm_type": "postpaid"},
    {"machine_name": "CM162-Server_CM_Postpaid", "user": "ptadwl12", "host": "tcsloawleapp1", "cm_type": "postpaid"},
    {"machine_name": "CM163-Server_CM_Postpaid", "user": "ptadwl13", "host": "tcsloawleapp1", "cm_type": "postpaid"},
    {"machine_name": "CM171-Server_CM_Postpaid", "user": "ptadwl21", "host": "tcsloawleapp2", "cm_type": "postpaid"},
    {"machine_name": "CM172-Server_CM_Postpaid", "user": "ptadwl22", "host": "tcsloawleapp2", "cm_type": "postpaid"},
    {"machine_name": "CM173-Server_CM_Postpaid", "user": "ptadwl23", "host": "tcsloawleapp2", "cm_type": "postpaid"},
]

CM_WL_BY_MACHINE = {item["machine_name"]: item for item in CM_WL_INSTANCES}

K8S_ACTIONS = ("check", "stop", "start", "restart")
WL_ACTIONS = ("check", "stop", "start", "restart")
DAEMON_ACTIONS = ("check", "stop", "start", "restart")
WL_PROPERTIES_ACTIONS = ("list", "read", "preview", "apply")
