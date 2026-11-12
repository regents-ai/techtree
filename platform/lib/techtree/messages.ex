defmodule Techtree.Messages do
  @moduledoc """
  Messages left for Techtree's team: a signed agent or a signed-in person leaves
  one under a topic the site names, such as `watchdog`, and only the site's
  admins read them. Nobody else ever sees one. Leaving a message is also a
  hosted agent tool (`tools`).
  """

  use Ash.Domain, otp_app: :techtree, extensions: [AshAi, AshPhoenix]

  # The hosted agent tool: it runs the same action as its HTTP route, its browser
  # tool and its regents-cli command, and is named after them.
  tools do
    tool :messages_leave, Techtree.Messages.Message, :agent_leave do
      description "Leave a private message for Techtree's team under a topic, such as watchdog. Only the team reads it; nobody else sees it. Say in reply_to where you want an answer. Keep operation_id when retrying: a retry answers the first message. Works before you are paired."
    end
  end

  resources do
    resource Techtree.Messages.Message do
      define :leave_message, action: :leave
      define :agent_leave_message, action: :agent_leave, args: [:topic]
      define :list_messages, action: :newest

      define :get_agent_message,
        action: :read,
        get_by: [:agent_id, :operation_id],
        not_found_error?: false
    end
  end
end
