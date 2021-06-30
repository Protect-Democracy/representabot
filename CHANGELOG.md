# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v0.3.2-beta] - 2021-06-29
### Added
- This CHANGELOG, TERMS, and CONTRIBUTING documentation to support open sourcing this project (representabot#17).
- Basic unit tests for data.py — it's a start! (representabot#19).
- Pre-commit hook to run unit tests.

### Changed
- Made maximum number of tweets per run configurable with `MAX_TWEETS` environment variable.
- More improvements to the tweet format and text (representabot#16).
- Better exception handling for failed S3 bucket access (representabot#18).
