// The app's shell: a rail at the left, then one of two pages. The browser page has the agent's
// browser in the middle and its chat at the right; the computer page is the desktop the agent works
// on, with its chat, across both. They are views of the desktop app laid over the empty frames drawn
// here; the shell tells the app where those frames are.

import { ArrowLeft, ArrowRight, Globe, Lock, Monitor, MonitorSmartphone, PlaneTakeoff, ReceiptText, RotateCw } from 'lucide-react';
import { useEffect, useRef, useState, type RefObject } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { TooltipProvider } from '@/components/ui/tooltip';

import type { DesktopPage, DesktopState, Rect } from './desktop';

const W = {
  product: 'BAP Browser',
  agent: 'Agent',
  browser: 'Browser',
  computer: 'Computer',
  computerTitle: 'The desktop the agent works on',
  tryItOn: 'Try it on',
  checkin: 'Skylark Air check-in',
  signup: 'Northfield sign-up',
  back: 'Back',
  forward: 'Forward',
  reload: 'Reload',
  address: 'Address',
  core: { starting: 'Starting', running: 'Connected', stopped: 'Stopped' },
  starting: 'Starting the agent…',
  startingHint: 'The chat appears here in a moment.',
  stopped: 'The agent is not running',
  startAgain: 'Start again',
  browserStarting: "The agent's browser",
} as const;

const NOWHERE: DesktopState = { core: 'starting', message: '', address: '', canGoBack: false, canGoForward: false, page: 'browser' };

function rectOf(element: HTMLElement | null): Rect {
  const box = element?.getBoundingClientRect();
  return box ? { x: box.x, y: box.y, width: box.width, height: box.height } : { x: 0, y: 0, width: 0, height: 0 };
}

/** Tells the desktop app where the two frames are, now and whenever either moves or changes size. */
function usePlacing(agent: RefObject<HTMLDivElement | null>, chat: RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    const place = () => window.desktop.place({ agent: rectOf(agent.current), chat: rectOf(chat.current) });
    const watching = new ResizeObserver(place);
    for (const frame of [agent.current, chat.current, document.body]) if (frame) watching.observe(frame);
    // The rail opening or closing moves the frames without changing the window.
    const moving = new MutationObserver(place);
    moving.observe(document.body, { attributes: true, subtree: true, attributeFilter: ['data-state'] });
    window.addEventListener('transitionend', place);
    place();
    return () => {
      watching.disconnect();
      moving.disconnect();
      window.removeEventListener('transitionend', place);
    };
  }, [agent, chat]);
}

export function App() {
  const [state, setState] = useState<DesktopState>(NOWHERE);
  const agentFrame = useRef<HTMLDivElement>(null);
  const chatFrame = useRef<HTMLDivElement>(null);
  useEffect(() => window.desktop.onState(setState), []);
  usePlacing(agentFrame, chatFrame);

  const running = state.core === 'running';
  // Nothing of a task sent the agent's browser anywhere yet: there is no real address to show.
  const hasPage = state.address !== '' && state.address !== 'about:blank';
  const secure = state.address.startsWith('https://');
  const onTheComputer = state.page === 'computer';
  const show = (page: DesktopPage) => window.desktop.show(page);
  // A page of the demo site is in the browser: the browser's page is shown with it.
  const open = (page: 'start' | 'checkin' | 'signup') => {
    show('browser');
    window.desktop.go('open', page);
  };

  return (
    <TooltipProvider>
      {/* The OS draws no title bar of its own (frame: false): this strip is dragged instead, and
          leaves its right edge to the window controls the OS overlays on top of it. */}
      <div className="app-drag flex h-9 shrink-0 items-center gap-2 pl-3 text-sm font-medium">
        <span className="size-4 shrink-0 rounded-sm" style={{ background: 'var(--brand-gradient)' }} aria-hidden="true" />
        <span className="truncate">{W.product}</span>
      </div>
      {/* The sidebar below positions itself `fixed`, which is otherwise relative to the window, not
          to this strip's height: `contain: layout` gives it this box as its containing block instead. */}
      <div className="min-h-0 flex-1" style={{ contain: 'layout' }}>
      <SidebarProvider defaultOpen={false} className="h-full min-h-0">
        <Sidebar collapsible="icon">
          <SidebarHeader>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton size="lg" className="pointer-events-none">
                  <span className="size-8 shrink-0 rounded-lg" style={{ background: 'var(--brand-gradient)' }} aria-hidden="true" />
                  <span className="truncate font-semibold tracking-tight">{W.product}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>{W.agent}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton isActive={!onTheComputer} tooltip={W.browser} onClick={() => show('browser')}>
                      <MonitorSmartphone />
                      <span>{W.browser}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton isActive={onTheComputer} tooltip={W.computer} onClick={() => show('computer')}>
                      <Monitor />
                      <span>{W.computer}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
            <SidebarGroup>
              <SidebarGroupLabel>{W.tryItOn}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton onClick={() => open('checkin')} disabled={!running}>
                      <PlaneTakeoff />
                      <span>{W.checkin}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton onClick={() => open('signup')} disabled={!running}>
                      <ReceiptText />
                      <span>{W.signup}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter>
            <Badge variant="outline" className="mx-auto gap-1.5 group-data-[collapsible=icon]:px-1.5" data-testid="core-status">
              <span className={`size-2 rounded-full ${running ? 'bg-success' : state.core === 'stopped' ? 'bg-destructive' : 'bg-warning'}`} aria-hidden="true" />
              <span className="group-data-[collapsible=icon]:hidden">{W.core[state.core]}</span>
            </Badge>
          </SidebarFooter>
        </Sidebar>

        <SidebarInset className="h-full min-w-0">
          <header className="flex h-14 shrink-0 items-center gap-1 px-3">
            <SidebarTrigger />
            {onTheComputer ? (
              <h1 className="ml-1 truncate text-sm font-semibold" data-testid="page-title">
                {W.computerTitle}
              </h1>
            ) : hasPage ? (
              <>
                <Button variant="ghost" size="icon" title={W.back} aria-label={W.back} disabled={!state.canGoBack} onClick={() => window.desktop.go('back')}>
                  <ArrowLeft />
                </Button>
                <Button variant="ghost" size="icon" title={W.forward} aria-label={W.forward} disabled={!state.canGoForward} onClick={() => window.desktop.go('forward')}>
                  <ArrowRight />
                </Button>
                <Button variant="ghost" size="icon" title={W.reload} aria-label={W.reload} disabled={!running} onClick={() => window.desktop.go('reload')}>
                  <RotateCw />
                </Button>
                <div className="ml-1 flex h-9 min-w-0 flex-1 items-center gap-2 rounded-full bg-secondary px-4 text-sm" role="group" aria-label={W.address}>
                  {secure ? <Lock className="size-4 shrink-0 text-muted-foreground" /> : <Globe className="size-4 shrink-0 text-muted-foreground" />}
                  <span className="truncate font-mono text-[13px]" data-testid="address">
                    {state.address}
                  </span>
                </div>
              </>
            ) : null}
          </header>

          <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1 px-3 pb-3">
            <ResizablePanel defaultSize="70" minSize="40">
              <div ref={agentFrame} className="grid h-full place-items-center rounded-xl border bg-secondary text-sm text-muted-foreground" data-testid="agent-frame">
                {W.browserStarting}
              </div>
            </ResizablePanel>
            <ResizableHandle className="mx-1.5 bg-transparent" />
            <ResizablePanel defaultSize="30" minSize="22">
              <div ref={chatFrame} className="grid h-full place-items-center rounded-xl border bg-secondary p-6 text-center" data-testid="chat-frame">
                {state.core === 'stopped' ? (
                  <div className="flex max-w-xs flex-col items-center gap-3">
                    <p className="font-semibold">{W.stopped}</p>
                    <p className="text-sm text-muted-foreground" data-testid="core-message">
                      {state.message}
                    </p>
                    <Button onClick={() => window.desktop.startAgain()}>{W.startAgain}</Button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-1">
                    <p className="font-semibold">{W.starting}</p>
                    <p className="text-sm text-muted-foreground">{W.startingHint}</p>
                  </div>
                )}
              </div>
            </ResizablePanel>
          </ResizablePanelGroup>
        </SidebarInset>
      </SidebarProvider>
      </div>
    </TooltipProvider>
  );
}
