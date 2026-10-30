"""PROPOSED successor-only Tomcat patch; no sealed parent modifications."""
import hashlib
PATH='backend/pom.xml'
EXPECTED_PARENT_POM_SHA256='f001883364ec2bbe1ef4ed32f9c995101cab3236614017308e66b3f49ad1b976'
def apply(templates):
    original=templates[PATH]
    if hashlib.sha256(original.encode()).hexdigest()!=EXPECTED_PARENT_POM_SHA256 or original.count('<properties>')!=1:
        raise ValueError('DEPENDENCY_TEMPLATE_DRIFT')
    result=dict(templates)
    result[PATH]=original.replace('<properties>','<properties><tomcat.version>11.0.26</tomcat.version>',1)
    return result
