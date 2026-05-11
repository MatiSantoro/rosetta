from __future__ import annotations

from typing import Dict, List, Literal, Optional

from samtranslator.internal.schema_source.common import (
    BaseModel,
    DictStrAny,
    PassThroughProp,
    ResourceAttributes,
    SamIntrinsicable,
    get_prop,
)

# TODO add docs

auth_spec = get_prop("sam-property-websocketapi-authconfiguration")
route_spec = get_prop("sam-property-websocketapi-routeconfiguration")
route53 = get_prop("sam-property-gatewayv2-route53configuration")
domain = get_prop("sam-property-gatewayv2-domainconfiguration")
properties = get_prop("sam-resource-websocketapi")

"""
Route53 and Domain are the exact same as in httpapi, which is why their get_prop refers to gatewayv2,
but implementing this for the underlying schema causes a failure when make schema checks to see if resources
are subclasses of the generator they're under, so they stay distinct for now.
"""


class Route53(BaseModel):
    EvaluateTargetHealth: Optional[PassThroughProp] = route53("EvaluateTargetHealth")
    HostedZoneId: Optional[PassThroughProp] = route53("HostedZoneId")
    HostedZoneName: Optional[PassThroughProp] = route53("HostedZoneName")
    IpV6: Optional[bool] = route53("IpV6")
    Region: Optional[PassThroughProp] = route53("Region")
    SetIdentifier: Optional[PassThroughProp] = route53("SetIdentifier")


class Domain(BaseModel):
    BasePath: Optional[List[str]] = domain("BasePath")
    CertificateArn: PassThroughProp = domain("CertificateArn")
    DomainName: PassThroughProp = domain("DomainName")
    EndpointConfiguration: Optional[SamIntrinsicable[Literal["REGIONAL"]]] = domain("EndpointConfiguration")
    MutualTlsAuthentication: Optional[PassThroughProp] = domain("MutualTlsAuthentication")
    OwnershipVerificationCertificateArn: Optional[PassThroughProp] = domain("OwnershipVerificationCertificateArn")
    Route53: Optional[Route53] = domain("Route53")
    SecurityPolicy: Optional[PassThroughProp] = domain("SecurityPolicy")


class AuthConfig(BaseModel):
    AuthArn: Optional[SamIntrinsicable[str]] = auth_spec("AuthArn")
    AuthType: PassThroughProp = auth_spec("AuthType")
    InvokeRole: Optional[SamIntrinsicable[str]] = auth_spec("InvokeRole")
    IdentitySource: Optional[PassThroughProp] = auth_spec("IdentitySource")
    Name: Optional[PassThroughProp] = auth_spec("Name")


class WebSocketApiRoute(BaseModel):
    ApiKeyRequired: Optional[PassThroughProp] = route_spec("ApiKeyRequired")
    FunctionArn: SamIntrinsicable[str] = route_spec("FunctionArn")
    IntegrationTimeout: Optional[PassThroughProp] = route_spec("IntegrationTimeout")
    ModelSelectionExpression: Optional[PassThroughProp] = route_spec("ModelSelectionExpression")
    OperationName: Optional[PassThroughProp] = route_spec("OperationName")
    RequestModels: Optional[PassThroughProp] = route_spec("RequestModels")
    RequestParameters: Optional[PassThroughProp] = route_spec("RequestParameters")
    RouteResponseSelectionExpression: Optional[PassThroughProp] = route_spec("RouteResponseSelectionExpression")


ApiKeySelectionExpression = Optional[PassThroughProp]
AccessLogSettings = Optional[PassThroughProp]
DefaultRouteSettings = Optional[PassThroughProp]
IpAddressType = Optional[PassThroughProp]
RouteSettings = Optional[PassThroughProp]
RouteSelectionExpression = Optional[PassThroughProp]
StageVariables = Optional[PassThroughProp]
Tags = Optional[DictStrAny]


class Properties(BaseModel):
    ApiKeySelectionExpression: Optional[PassThroughProp] = properties("ApiKeySelectionExpression")
    AccessLogSettings: Optional[AccessLogSettings] = properties("AccessLogSettings")
    Auth: Optional[AuthConfig] = properties("Auth")
    DefaultRouteSettings: Optional[RouteSettings] = properties("DefaultRouteSettings")
    Description: Optional[str] = properties("Description")
    DisableExecuteApiEndpoint: Optional[PassThroughProp] = properties("DisableExecuteApiEndpoint")
    Domain: Optional[Domain] = properties("Domain")
    DisableSchemaValidation: Optional[bool] = properties("DisableSchemaValidation")
    IpAddressType: Optional[PassThroughProp] = properties("IpAddressType")
    Name: Optional[PassThroughProp] = properties("Name")
    PropagateTags: Optional[bool] = properties("PropagateTags")
    Routes: Dict[str, WebSocketApiRoute] = properties("Routes")
    RouteSelectionExpression: PassThroughProp = properties("RouteSelectionExpression")
    RouteSettings: Optional[RouteSettings] = properties("RouteSettings")
    StageName: Optional[PassThroughProp] = properties("StageName")
    StageVariables: Optional[StageVariables] = properties("StageVariables")
    Tags: Optional[Tags] = properties("Tags")


class Globals(BaseModel):
    ApiKeySelectionExpression: Optional[str] = properties("ApiKeySelectionExpression")
    AccessLogSettings: Optional[AccessLogSettings] = properties("AccessLogSettings")
    DefaultRouteSettings: Optional[RouteSettings] = properties("DefaultRouteSettings")
    DisableExecuteApiEndpoint: Optional[bool] = properties("DisableExecuteApiEndpoint")
    DisableSchemaValidation: Optional[bool] = properties("DisableSchemaValidation")
    Domain: Optional[Domain] = properties("Domain")
    IpAddressType: Optional[str] = properties("IpAddressType")
    PropagateTags: Optional[bool] = properties("PropagateTags")
    RouteSettings: Optional[RouteSettings] = properties("RouteSettings")
    RouteSelectionExpression: Optional[str] = properties("RouteSelectionExpression")
    StageVariables: Optional[StageVariables] = properties("StageVariables")
    Tags: Optional[Tags] = properties("Tags")


class Resource(ResourceAttributes):
    Type: Literal["AWS::Serverless::WebSocketApi"]
    Properties: Optional[Properties]
