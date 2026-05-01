import * as cdk from 'aws-cdk-lib'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as logs from 'aws-cdk-lib/aws-logs'
import { Construct } from 'constructs'

export class AppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props)

    // ── Storage ───────────────────────────────────────────────────────────────

    const dataBucket = new s3.Bucket(this, 'DataBucket', {
      versioned:          true,
      encryption:         s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess:  s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy:      cdk.RemovalPolicy.RETAIN,
    })

    const jobsTable = new dynamodb.Table(this, 'JobsTable', {
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey:      { name: 'jobId',  type: dynamodb.AttributeType.STRING },
      billingMode:  dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'expiresAt',
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    })

    jobsTable.addGlobalSecondaryIndex({
      indexName:    'status-updatedAt-index',
      partitionKey: { name: 'status',    type: dynamodb.AttributeType.STRING },
      sortKey:      { name: 'updatedAt', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    })

    // ── Compute ───────────────────────────────────────────────────────────────

    const processorRole = new iam.Role(this, 'ProcessorRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    })

    const logGroup = new logs.LogGroup(this, 'ProcessorLogGroup', {
      logGroupName:  `/aws/lambda/${this.stackName}-processor`,
      retention:     logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    })

    const processor = new lambda.Function(this, 'ProcessorFunction', {
      functionName: `${this.stackName}-processor`,
      runtime:      lambda.Runtime.PYTHON_3_13,
      handler:      'handler.handler',
      role:         processorRole,
      timeout:      cdk.Duration.seconds(30),
      memorySize:   256,
      architecture: lambda.Architecture.ARM_64,
      // Code must be provided separately
      code: lambda.Code.fromAsset('placeholder'),
      environment: {
        JOBS_TABLE:  jobsTable.tableName,
        DATA_BUCKET: dataBucket.bucketName,
      },
      logGroup,
    })

    // Grant permissions using CDK grant methods
    jobsTable.grantReadWriteData(processor)
    dataBucket.grantReadWrite(processor)

    // ── Outputs ───────────────────────────────────────────────────────────────

    new cdk.CfnOutput(this, 'BucketName', {
      value:       dataBucket.bucketName,
      description: 'Name of the data S3 bucket',
      exportName:  `${this.stackName}-BucketName`,
    })

    new cdk.CfnOutput(this, 'TableName', {
      value:       jobsTable.tableName,
      description: 'Name of the DynamoDB jobs table',
      exportName:  `${this.stackName}-TableName`,
    })

    new cdk.CfnOutput(this, 'FunctionArn', {
      value:       processor.functionArn,
      description: 'ARN of the processor Lambda function',
      exportName:  `${this.stackName}-FunctionArn`,
    })
  }
}
