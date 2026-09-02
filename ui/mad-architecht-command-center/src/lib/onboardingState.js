import { useState, useEffect } from 'react'

/**
 * useOnboardingState — track user's first-time onboarding flow
 * Persists to localStorage so modal only shows once
 */
export function useOnboardingState() {
  const [hasSeenOnboarding, setHasSeenOnboarding] = useState(false)
  const [selectedRole, setSelectedRole] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  // Load onboarding state from localStorage
  useEffect(() => {
    if (typeof window === 'undefined') {
      setIsLoading(false)
      return
    }

    try {
      const seen = localStorage.getItem('mammoth_onboarding_complete')
      const role = localStorage.getItem('mammoth_user_role')
      
      if (seen === 'true') {
        setHasSeenOnboarding(true)
      }
      
      if (role) {
        setSelectedRole(role)
      }

      setIsLoading(false)
    } catch {
      setIsLoading(false)
    }
  }, [])

  // Mark onboarding as complete
  const completeOnboarding = (role) => {
    try {
      localStorage.setItem('mammoth_onboarding_complete', 'true')
      if (role) {
        localStorage.setItem('mammoth_user_role', role.id || role)
        setSelectedRole(role.id || role)
      }
    } catch {
      // storage errors should not break the flow
    }
    setHasSeenOnboarding(true)
  }

  // Reset onboarding (for testing/reset scenarios)
  const resetOnboarding = () => {
    try {
      localStorage.removeItem('mammoth_onboarding_complete')
      localStorage.removeItem('mammoth_user_role')
    } catch {
      // no-op
    }
    setHasSeenOnboarding(false)
    setSelectedRole(null)
  }

  return {
    hasSeenOnboarding,
    selectedRole,
    isLoading,
    completeOnboarding,
    resetOnboarding,
  }
}

/**
 * getRolePresetConfig — load user's preferred interface based on selected role
 */
export function getRolePresetConfig(roleId) {
  const configs = {
    learner: {
      defaultPage: 'lessons',
      contextPanelsCollapsed: true,
      showProgressBars: true,
      showMobileFriendlyDefaults: true,
      toolsOrder: ['lessons', 'atlas', 'flashcards', 'notes'],
    },
    builder: {
      defaultPage: 'chat',
      contextPanelsCollapsed: true,
      showExecutionConfidence: true,
      showRepositoryContext: true,
      toolsOrder: ['chat', 'agent', 'commandlib', 'artifacts'],
    },
    operator: {
      defaultPage: 'agent',
      contextPanelsCollapsed: true,
      showApprovalGates: true,
      showAuditTrail: true,
      showHealth: true,
      toolsOrder: ['agent', 'health', 'diagnostics', 'manual'],
    },
    founder: {
      defaultPage: 'landing',
      contextPanelsCollapsed: false,
      showAllFeatures: true,
      showProductStory: true,
      toolsOrder: ['landing', 'lessons', 'chat', 'agent', 'manual'],
    },
  }

  return configs[roleId] || configs.learner
}
