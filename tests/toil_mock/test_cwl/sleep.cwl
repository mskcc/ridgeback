cwlVersion: v1.0
class: Workflow
id: simpleWorkflow

inputs:
  sleepSeconds:
    type: string[]

steps:
  sleep:
    run:
      class: CommandLineTool
      id: sleep
      inputs:
        time:
          type: string
      baseCommand: [sleep]
      arguments: [ $(inputs.time)]
      outputs: []
    in:
      time:
        source: sleepSeconds
    scatter: [time]
    out: []

outputs: []

requirements:
  - class: ScatterFeatureRequirement
  - class: MultipleInputFeatureRequirement
