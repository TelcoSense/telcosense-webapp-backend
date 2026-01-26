# telcosense-webapp-backend

Backend for the TelcoSense web application.

## Overview

This repository contains backend components for the TelcoSense web application, providing APIs and background services for data access, processing, and orchestration. The backend serves as the integration layer between data storage systems, processing pipelines, and the web-based visualization frontend.

It is designed for modular deployment and supports multiple data domains used within the TelcoSense platform.

## Environment Setup

The backend is implemented in Python and is intended to run within a Conda-managed environment.

- Conda
- Python == 3.10.8

Additional dependencies are specified in the environment configuration files included in the repository.

## Contents

- Web API services
- Data access and integration logic
- Background tasks and processing helpers
- Configuration and deployment-related scripts

## Usage

The backend services are typically deployed as part of the complete TelcoSense platform.  
Setup and execution details depend on the target environment and are documented inline or in accompanying configuration files.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Acknowledgements

This output was financed through the projects “Precipitation Detection and Quantification System Based on Networks of Microwave Links” (SS06020416) and “Spatial Air Temperature Monitoring Using Microwave Links Data” (SS07020434), which are co-funded with state support from the Technology Agency of the Czech Republic under the Environment for Life Programme and further funded within the National Recovery Plan from the European Recovery and Resilience Facility.

<p align="center">
  <img src="assets/tacr.png" alt="Technology Agency of the Czech Republic" height="64" />
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/eu.png" alt="European Union" height="64" />
</p>