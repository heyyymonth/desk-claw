import { expect, type Page, test } from '@playwright/test';

type Priority = 'low' | 'normal' | 'high' | 'urgent';
type Decision = 'schedule' | 'decline' | 'clarify' | 'defer';
type RiskLevel = 'low' | 'medium' | 'high';

interface Scenario {
  name: string;
  rawText: string;
  intent: {
    title: string;
    requester: string;
    duration_minutes: number;
    priority: Priority;
    attendees: string[];
    constraints: string[];
    missing_fields: string[];
  };
  recommendation: {
    decision: Decision;
    risk: RiskLevel;
    riskMessage: string;
    rationale: string[];
    proposedSlot?: {
      start: string;
      end: string;
      reason: string;
    };
  };
  draftBody: string;
  feedback: 'Accept' | 'Edited';
  expectedLogDecision: 'accepted' | 'edited';
}

const rules = {
  executive_name: 'Executive',
  timezone: 'America/Los_Angeles',
  working_hours: { start: '09:00', end: '17:00' },
  protected_blocks: [
    {
      label: 'CEO focus block',
      start: '2026-05-11T09:00:00-07:00',
      end: '2026-05-11T11:00:00-07:00',
    },
    {
      label: 'Board prep',
      start: '2026-05-12T14:00:00-07:00',
      end: '2026-05-12T16:00:00-07:00',
    },
  ],
  preferences: [
    'Prefer investor and customer meetings before 2 PM.',
    'Avoid scheduling over protected blocks.',
    'Ask for clarification when requester, purpose, or duration is missing.',
  ],
};

const calendar = {
  busy_blocks: [
    {
      title: 'Leadership sync',
      start: '2026-05-11T13:00:00-07:00',
      end: '2026-05-11T14:00:00-07:00',
    },
    {
      title: 'Product review',
      start: '2026-05-12T10:00:00-07:00',
      end: '2026-05-12T11:30:00-07:00',
    },
  ],
  assumptions: ['Seeded local mock calendar only.'],
  missing_context: [],
};

const scenarios: Scenario[] = [
  {
    name: 'vague external request',
    rawText: 'Can the exec meet sometime next week? Sent by Taylor at partner@example.com.',
    intent: {
      title: 'Meeting request',
      requester: 'Taylor',
      duration_minutes: 30,
      priority: 'normal',
      attendees: ['partner@example.com'],
      constraints: ['Requested for next week'],
      missing_fields: ['purpose'],
    },
    recommendation: {
      decision: 'clarify',
      risk: 'medium',
      riskMessage: 'Purpose is unclear for an external requester.',
      rationale: ['Request is external but vague.', 'Clarification is needed before offering executive time.'],
    },
    draftBody: 'Thanks for reaching out. Could you share the purpose and desired attendees before we look for time?',
    feedback: 'Accept',
    expectedLogDecision: 'accepted',
  },
  {
    name: 'customer escalation',
    rawText: 'Urgent customer escalation from Alex Morgan for 30 minutes next week, preferably morning.',
    intent: {
      title: 'Customer escalation',
      requester: 'Alex Morgan',
      duration_minutes: 30,
      priority: 'urgent',
      attendees: [],
      constraints: ['Requested for next week', 'Prefers morning'],
      missing_fields: [],
    },
    recommendation: {
      decision: 'schedule',
      risk: 'low',
      riskMessage: 'Urgent customer issue should be reviewed before send.',
      rationale: ['Urgent customer escalation.', 'Found a slot outside protected blocks.'],
      proposedSlot: {
        start: '2026-05-11T11:00:00-07:00',
        end: '2026-05-11T11:30:00-07:00',
        reason: 'First safe mock-calendar slot after focus time.',
      },
    },
    draftBody: 'Thanks for the escalation context. We can offer Monday, May 11 at 11:00 AM PT for 30 minutes.',
    feedback: 'Accept',
    expectedLogDecision: 'accepted',
  },
  {
    name: 'investor during board prep',
    rawText: 'Important investor meeting from Maya Chen for 45 minutes next week during board prep.',
    intent: {
      title: 'Investor meeting',
      requester: 'Maya Chen',
      duration_minutes: 45,
      priority: 'high',
      attendees: [],
      constraints: ['Requested for next week', 'Conflicts with board prep'],
      missing_fields: [],
    },
    recommendation: {
      decision: 'schedule',
      risk: 'medium',
      riskMessage: 'Investor request is important, but board prep is protected.',
      rationale: ['Investor priority is high.', 'Avoided the protected board prep block.'],
      proposedSlot: {
        start: '2026-05-12T11:30:00-07:00',
        end: '2026-05-12T12:15:00-07:00',
        reason: 'Avoids board prep and product review.',
      },
    },
    draftBody: 'We can offer Tuesday, May 12 at 11:30 AM PT and will avoid the board prep window.',
    feedback: 'Edited',
    expectedLogDecision: 'edited',
  },
  {
    name: 'internal recurring sync that should be challenged',
    rawText: 'Internal recurring sync from Jordan Lee for 60 minutes every week with no agenda.',
    intent: {
      title: 'Internal recurring sync',
      requester: 'Jordan Lee',
      duration_minutes: 60,
      priority: 'normal',
      attendees: [],
      constraints: ['Recurring request', 'No agenda supplied'],
      missing_fields: ['agenda'],
    },
    recommendation: {
      decision: 'clarify',
      risk: 'medium',
      riskMessage: 'Recurring internal sync lacks an agenda and should be challenged.',
      rationale: ['Recurring meeting load should be reviewed.', 'Ask for agenda before committing executive time.'],
    },
    draftBody: 'Could you send the agenda and confirm whether this needs executive attendance every week?',
    feedback: 'Accept',
    expectedLogDecision: 'accepted',
  },
  {
    name: 'missing context request',
    rawText: 'Need time with the exec. No requester, duration, or purpose was included.',
    intent: {
      title: 'Meeting request',
      requester: 'Unknown requester',
      duration_minutes: 30,
      priority: 'normal',
      attendees: [],
      constraints: [],
      missing_fields: ['requester', 'purpose'],
    },
    recommendation: {
      decision: 'clarify',
      risk: 'medium',
      riskMessage: 'Request is missing requester and purpose.',
      rationale: ['Missing context blocks scheduling.', 'Clarification is required before recommendation.'],
    },
    draftBody: 'Could you share who is requesting the meeting, the purpose, and any timing constraints?',
    feedback: 'Accept',
    expectedLogDecision: 'accepted',
  },
];

function recommendationFor(scenario: Scenario) {
  return {
    decision: scenario.recommendation.decision,
    confidence: scenario.recommendation.decision === 'schedule' ? 0.86 : 0.73,
    rationale: scenario.recommendation.rationale,
    risks: [
      {
        level: scenario.recommendation.risk,
        message: scenario.recommendation.riskMessage,
      },
    ],
    proposed_slots: scenario.recommendation.proposedSlot ? [scenario.recommendation.proposedSlot] : [],
    model_status: 'not_configured',
  };
}

async function installApiMocks(page: Page, options?: { backendUnavailable?: boolean; ollamaUnavailable?: boolean }) {
  const decisions: unknown[] = [];

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (options?.backendUnavailable) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Backend unavailable' }) });
      return;
    }

    if (url.pathname === '/api/health') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ok', ollama: options?.ollamaUnavailable ? 'unavailable' : 'mocked' }),
      });
      return;
    }

    if (url.pathname === '/api/default-rules') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(rules) });
      return;
    }

    if (url.pathname === '/api/mock-calendar') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(calendar) });
      return;
    }

    if (url.pathname === '/api/decisions' && request.method() === 'GET') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(decisions) });
      return;
    }

    if (url.pathname === '/api/parse-request') {
      const body = request.postDataJSON() as { raw_text: string };
      const scenario = scenarios.find((item) => item.rawText === body.raw_text) ?? scenarios[0];
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          raw_text: scenario.rawText,
          intent: { ...scenario.intent, preferred_windows: [] },
        }),
      });
      return;
    }

    if (url.pathname === '/api/recommendation') {
      const body = request.postDataJSON() as { meeting_request: { raw_text: string } };
      const scenario = scenarios.find((item) => item.rawText === body.meeting_request.raw_text) ?? scenarios[0];
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(recommendationFor(scenario)) });
      return;
    }

    if (url.pathname === '/api/draft-response') {
      const body = request.postDataJSON() as { meeting_request: { raw_text: string } };
      const scenario = scenarios.find((item) => item.rawText === body.meeting_request.raw_text) ?? scenarios[0];
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          subject: `Re: ${scenario.intent.title}`,
          body: scenario.draftBody,
          tone: scenario.recommendation.decision === 'schedule' ? 'warm' : 'concise',
          model_status: 'not_configured',
        }),
      });
      return;
    }

    if (url.pathname === '/api/decisions' && request.method() === 'POST') {
      const entry = {
        id: decisions.length + 1,
        created_at: '2026-05-08T17:00:00-07:00',
        ...(request.postDataJSON() as object),
      };
      decisions.unshift(entry);
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(entry) });
      return;
    }

    await route.fulfill({ status: 404, body: 'Unhandled mocked route' });
  });
}

async function completeWorkflow(page: Page, scenario: Scenario) {
  await page.goto('/');

  await page.getByLabel('Meeting request').fill(scenario.rawText);
  await page.getByRole('button', { name: 'Parse Request' }).click();

  await expect(page.getByText(scenario.intent.title).first()).toBeVisible();
  await expect(page.getByText(scenario.intent.requester).first()).toBeVisible();
  await expect(page.getByText(new RegExp(scenario.intent.priority, 'i')).first()).toBeVisible();

  await expect(page.getByText('Prefer investor and customer meetings before 2 PM.')).toBeVisible();
  await page.getByRole('button', { name: 'Confirm executive rules' }).click();
  await expect(page.getByLabel('Busy block 1 title')).toHaveValue('Leadership sync');
  await page.getByRole('button', { name: 'Confirm mock calendar' }).click();

  await page.getByRole('button', { name: 'Generate Recommendation' }).click();
  await expect(page.getByText(new RegExp(`^${scenario.recommendation.decision}$`, 'i')).first()).toBeVisible();
  await expect(page.getByText(scenario.recommendation.riskMessage)).toBeVisible();
  await expect(page.getByText('Rationale')).toBeVisible();
  await expect(page.getByText('Calendar impact', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Generate Draft' }).click();
  await expect(page.getByLabel('Draft body')).toHaveValue(scenario.draftBody);

  if (scenario.feedback === 'Edited') {
    await page.getByLabel('Draft body').fill(`${scenario.draftBody} Please confirm this works.`);
  }

  await page.getByRole('button', { name: scenario.feedback }).click();
  const logEntry = page
    .locator('article')
    .filter({ hasText: `${scenario.recommendation.decision} recommendation for ${scenario.intent.requester}` })
    .first();
  await expect(logEntry).toBeVisible();
  await expect(logEntry.getByText(scenario.expectedLogDecision, { exact: true })).toBeVisible();
}

test.describe('V0 scheduling workflow', () => {
  for (const scenario of scenarios) {
    test(scenario.name, async ({ page }) => {
      await installApiMocks(page);
      await completeWorkflow(page, scenario);
    });
  }

  test('backend unavailable error', async ({ page }) => {
    await installApiMocks(page, { backendUnavailable: true });
    await page.goto('/');

    await expect(page.getByText('Backend unavailable').first()).toBeVisible();
    await page.getByLabel('Meeting request').fill(scenarios[1].rawText);
    await page.getByRole('button', { name: 'Parse Request' }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'Backend unavailable' }).last()).toBeVisible();
  });

  test('Ollama unavailable mocked fallback state', async ({ page }) => {
    await installApiMocks(page, { ollamaUnavailable: true });
    await page.goto('/');

    await expect(page.getByText('Ollama: unavailable')).toBeVisible();
    await completeWorkflow(page, scenarios[0]);
  });
});
