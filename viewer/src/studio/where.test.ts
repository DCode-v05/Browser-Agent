import { describe, expect, it } from 'vitest';

import { whereItWorks } from './where';

describe('where the computer page works, said on the page', () => {
  it('names the engine by the machine that served the page, and this computer when it is this one', () => {
    expect(whereItWorks('remote', 'bap-browser-1.tail4d0a18.ts.net', 'https://sharans-macbook-pro.tail4d0a18.ts.net:8796')).toEqual({
      engine: 'bap-browser-1',
      target: 'sharans-macbook-pro, a machine elsewhere, through its helper',
    });
    expect(whereItWorks('machine', '127.0.0.1', '').engine).toBe('this computer');
    expect(whereItWorks('machine', 'localhost', '').target).toBe("the engine's own machine: its real screen");
  });

  it('says what each way of working drives', () => {
    expect(whereItWorks('here', 'bap-desk.tail4d0a18.ts.net', '').target).toBe("the engine's own Linux desktop");
    expect(whereItWorks('container', '127.0.0.1', '').target).toBe('a Linux desktop of its own, in a container beside the engine');
    expect(whereItWorks('remote', '127.0.0.1', '').target).toBe('a machine elsewhere, through its helper');
  });
});
