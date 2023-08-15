#!/bin/bash
set -euo pipefail
FAILURE=1
SUCCESS=0
SLACKWEBHOOKURL="https://hooks.slack.com/services/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"
#REPO_URL="https://gitlab.office.myjet.tech/production/pricing"
function print_slack_summary_build() {
    local slack_msg_header
    local slack_msg_body
    local slack_channel
# Populate header and define slack channels
slack_msg_header=":fu: *${PROJECT_NAME} | Build of ${ENVIRONMENT} failed*"
if [[ "${EXIT_STATUS}" == "${SUCCESS}" ]]; then
        slack_msg_header=":meow_wow: *${PROJECT_NAME} | Build of ${ENVIRONMENT} succeeded*"
        #slack_channel="test-noty-gitlab"
    fi
cat <<-SLACK
            {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "${slack_msg_header}"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": "*Stage:*\nBuild"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Pushed By:*\n${GITLAB_USER_NAME}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Job URL:*\n$CI_PROJECT_URL/-/jobs/${CI_JOB_ID}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Commit URL:*\n$CI_PROJECT_URL/commit/$(git rev-parse HEAD)"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Commit Branch:*\n${CI_COMMIT_REF_NAME}"
                            }
                        ]
                    },
                    {
                        "type": "divider"
                    }
                ]
}
SLACK
}
function share_slack_update_build() {
local slack_webhook
slack_webhook="$SLACKWEBHOOKURL"
curl -X POST                                           \
        --data-urlencode "payload=$(print_slack_summary_build)"  \
        "${slack_webhook}"
}


function print_slack_summary_deploy() {
    local slack_msg_header
    local slack_msg_body
    local slack_channel
# Populate header and define slack channels
slack_msg_header=":fu: *${PROJECT_NAME} | Deploy to ${ENVIRONMENT} failed*"
if [[ "${EXIT_STATUS}" == "${SUCCESS}" ]]; then
        slack_msg_header=":meow_wow: *${PROJECT_NAME} | Deploy to ${ENVIRONMENT} succeeded*"
        #slack_channel="test-noty-gitlab"
    fi
cat <<-SLACK
            {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "${slack_msg_header}"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": "*Stage:*\nBuild"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Pushed By:*\n${GITLAB_USER_NAME}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Job URL:*\n$CI_PROJECT_URL/-/jobs/${CI_JOB_ID}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Commit URL:*\n$CI_PROJECT_URL/commit/$(git rev-parse HEAD)"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Commit Branch:*\n${CI_COMMIT_REF_NAME}"
                            }
                        ]
                    },
                    {
                        "type": "divider"
                    }
                ]
}
SLACK
}
function share_slack_update_deploy() {
local slack_webhook
slack_webhook="$SLACKWEBHOOKURL"
curl -X POST                                           \
        --data-urlencode "payload=$(print_slack_summary_deploy)"  \
        "${slack_webhook}"
}