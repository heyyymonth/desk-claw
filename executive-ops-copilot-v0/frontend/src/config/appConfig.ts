import {
  Activity,
  CheckCircle2,
  ClipboardList,
  Gauge,
  Home,
  LockKeyhole,
  PenLine,
  Route,
  Settings,
  UserCircle,
  Workflow,
  type LucideIcon,
} from 'lucide-react';

export type PageId = 'home' | 'admin' | 'telemetry' | 'account' | 'settings';
export type PersonaId = 'executive_assistant' | 'admin';

export type Persona = {
  id: PersonaId;
  label: string;
  eyebrow: string;
  name: string;
  title: string;
  email: string;
  phone: string;
  timezone: string;
  role: string;
  accessLevel: string;
  lastActive: string;
};

export type PageDefinition = {
  id: PageId;
  label: string;
  detail: string;
  icon: LucideIcon;
};

export const starterRules = {
  executive_name: 'Executive',
  timezone: 'America/Los_Angeles',
  working_hours: { start: '09:00', end: '17:00' },
  protected_blocks: [],
  preferences: ['Avoid moving protected focus time without explicit approval.'],
};

export const workflowSteps = [
  {
    label: 'Paste the request',
    detail: 'Add the email or message exactly as received.',
    icon: ClipboardList,
  },
  {
    label: 'Review details',
    detail: 'Confirm requester, timing, risk, and missing context.',
    icon: CheckCircle2,
  },
  {
    label: 'Get guidance',
    detail: 'Generate a scheduling recommendation for review.',
    icon: Route,
  },
  {
    label: 'Prepare reply',
    detail: 'Draft, edit, and log the final human decision.',
    icon: PenLine,
  },
];

export const enterpriseSignals = [
  { label: 'Requests reviewed', value: '1.8k', detail: 'this quarter', icon: Activity },
  { label: 'Avg. cycle time', value: '4m', detail: 'request to draft', icon: Gauge },
  { label: 'Audit coverage', value: '100%', detail: 'human decision log', icon: LockKeyhole },
];

export const trustMarks = ['Northstar Ops', 'Atlas Finance', 'Forge AI', 'Helio Systems', 'Summit Cloud'];

export const pages: PageDefinition[] = [
  { id: 'home', label: 'Home', detail: 'Chat and calendar', icon: Home },
  { id: 'admin', label: 'Admin Center', detail: 'Intake, drafts, logs', icon: Workflow },
  { id: 'telemetry', label: 'AI Dashboard', detail: 'DB telemetry', icon: Gauge },
  { id: 'account', label: 'Account', detail: 'Plan and seats', icon: UserCircle },
  { id: 'settings', label: 'Settings', detail: 'Security and AI controls', icon: Settings },
];

export const commandPrompts = [
  'Find a safe 30 minute window with Support leadership.',
  'Summarize today\'s calendar risk before the 2 PM board prep.',
  'Draft a concise reply asking for missing attendee context.',
];

export const brandLogoSrc = '/brand/desk-ai-logo.jpeg';

export const personas: Record<PersonaId, Persona> = {
  executive_assistant: {
    id: 'executive_assistant',
    label: 'Executive Assistant',
    eyebrow: 'Executive assistant view',
    name: 'Maya Srinivasan',
    title: 'Executive Assistant to Dana Lee',
    email: 'maya.srinivasan@northstar-ops.example',
    phone: '+1 (415) 555-0142',
    timezone: 'America/Los_Angeles',
    role: 'Executive assistant',
    accessLevel: 'Meeting intake, calendar coordination, scheduling approvals',
    lastActive: 'Today at 2:41 PM Pacific',
  },
  admin: {
    id: 'admin',
    label: 'Workspace Admin',
    eyebrow: 'Admin view',
    name: 'Priya Shah',
    title: 'Workspace Admin, Executive Operations',
    email: 'priya.shah@northstar-ops.example',
    phone: '+1 (415) 555-0198',
    timezone: 'America/Los_Angeles',
    role: 'Workspace admin',
    accessLevel: 'Billing, rules, calendar assumptions, audit logs',
    lastActive: 'Today at 2:36 PM Pacific',
  },
};
