import { describe, expect, it } from '@jest/globals';
import { normalizeBrokerCredential } from './connection';

describe('normalizeBrokerCredential', () => {
  it('removes whitespace and pasted line breaks from API credentials', () => {
    expect(normalizeBrokerCredential(' F79 Fox\nIqh\tXFEp9c2GA ')).toBe('F79FoxIqhXFEp9c2GA');
  });
});
