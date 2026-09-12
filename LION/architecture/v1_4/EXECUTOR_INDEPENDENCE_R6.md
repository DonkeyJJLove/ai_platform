# Material executor independence — R6

Connector identity, host identity, boot/kernel domain, runtime instance, physical machine, control domain and material executor are separate layers. Four connector IDs or hostnames do not prove four machines. The current four WSL2 connectors share one boot ID, which falsifies boot-domain independence and leaves physical/material independence not proven. Even distinct boot IDs are insufficient; promotion requires current external attestations for at least two distinct runtime, physical and control domains with distinct trust anchors.
