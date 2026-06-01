import React from 'react'
import type { ConfirmationOption, ConfirmationRequest } from '../../agent/types'

interface AgentConfirmationMenuProps {
  request: ConfirmationRequest | null
  onSelect: (option: ConfirmationOption) => void
}

export default function AgentConfirmationMenu({
  request,
  onSelect,
}: AgentConfirmationMenuProps) {
  if (!request) return null

  return (
    <div
      className="agent-confirmation-menu"
      data-agent-confirmation-menu="true"
      role="menu"
      aria-label={request.title}
    >
      <div className="agent-confirmation-menu__header">
        <strong>{request.title}</strong>
        {request.message ? <span>{request.message}</span> : null}
      </div>
      <div className="agent-confirmation-menu__options">
        {request.options.map((option) => (
          <button
            key={option.id}
            type="button"
            className="agent-confirmation-menu__option"
            role="menuitem"
            onClick={() => onSelect(option)}
          >
            <strong>{option.label}</strong>
            {option.description ? <span>{option.description}</span> : null}
          </button>
        ))}
      </div>
    </div>
  )
}
