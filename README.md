# BUYMA Price Manager

A Python application that compares competitor prices on BUYMA and prepares controlled price updates for eligible BestShip listings.

## Features

- Reads competitor product URLs from Google Sheets
- Compares listed prices and calculates a target price using configurable rules
- Previews proposed changes before applying them
- Supports single-product and bulk update workflows through the BUYMA Personal Shopper Product API
- Stores execution summaries and product results in Google Sheets and CSV
- Provides a scheduler and Windows executable builds

## How pricing is controlled

The price rules are configured in config.yaml:

    app:
      price:
        delta: 10
        max_change: 50

- delta: the amount to undercut the competitor's lowest price
- max_change: the maximum reduction allowed in one run

The interactive workflow starts with a preview. Actual updates require confirmation. Time-sale products are handled according to the configured option.

## Requirements

- Windows
- Python 3.11
- uv
- BUYMA API credentials
- Google service-account credentials and access to the target spreadsheet

## Setup

    git clone https://github.com/BaeDoge/python-buyma-management.git
    cd python-buyma-management
    uv sync

Copy the example configuration files and fill in your own values:

    copy .env.example .env
    copy config.example.yaml config.yaml

Place the Google service-account credential file at secrets/service_account.json and configure the required BUYMA credentials locally. Never commit credentials, tokens, or populated configuration files.

## Run

Interactive price manager:

    uv run buyma_price_manager.py

Scheduled price manager:

    uv run buyma_price_scheduler.py

The scheduler runs on the local machine's clock and must remain running while scheduled tasks are expected to execute.

## Windows executable

Run the build script on Windows:

    build_exe.bat

The output executables are placed in dist/. See docs/USER_MANUAL.md for operational details and docs/BUILD_EXE.md for packaging information.

## Tests

    uv run pytest app/tests -q

The automated tests use mocked HTTP responses and Google Sheets objects. They do not update live BUYMA product prices. Live behaviour depends on account permissions, API availability, credentials, and the external service.

## Project layout

    buyma_price_manager.py       Interactive application entry point
    buyma_price_scheduler.py     Scheduled execution entry point
    config.example.yaml          Example application configuration
    app/                         Pricing, API, reporting, and scheduler modules
    app/tests/                   Automated tests
    docs/                        User and build documentation

## Security

Keep .env, config.yaml, and files under secrets/ out of version control. Use API credentials only in trusted environments and review the preview carefully before applying bulk changes.
