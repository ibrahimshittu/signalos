import { describe, expect, it, jest } from '@jest/globals';
import { render } from '@testing-library/react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import WelcomeScreen from '@/app/(onboarding)/welcome';

jest.mock('expo-router', () => ({ router: { push: jest.fn() } }));

const metrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, right: 0, bottom: 34, left: 0 },
};

describe('welcome experience', () => {
  it('pairs the accountable product promise with concise supporting context', async () => {
    const view = await render(
      <SafeAreaProvider initialMetrics={metrics}>
        <WelcomeScreen />
      </SafeAreaProvider>,
    );

    expect(
      view.getByRole('header', { name: /Market intelligence\.\s*Accountable to you\./ }),
    ).toBeTruthy();
    expect(view.getAllByRole('header')).toHaveLength(1);
    expect(view.getByRole('image', { name: 'SignalOS' })).toBeTruthy();
    expect(
      view.getByText('A clearer view of the market, shaped around your portfolio.'),
    ).toBeTruthy();
    expect(view.getByText('Analysis first. Orders only with your approval.')).toBeTruthy();
    expect(view.queryByText('An investment studio that has to convince you first.')).toBeNull();
    expect(view.queryByText('Evidence')).toBeNull();
    expect(view.queryByText('Opposing case')).toBeNull();
    expect(view.queryByText('Portfolio impact')).toBeNull();
  });
});
