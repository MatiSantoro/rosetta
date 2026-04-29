output "state_machine_arn" {
  description = "ARN of the Step Functions state machine. Pass to the lambda module so start_job can trigger it."
  value       = aws_sfn_state_machine.translate_job.arn
}

output "state_machine_name" {
  value = aws_sfn_state_machine.translate_job.name
}
