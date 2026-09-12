import { describe, expect, it } from '@jest/globals';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { Pressable } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Text } from './Text';
import { ToastProvider, useToast } from './Toast';

const metrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 },
};

function Harness() {
  const { dismissToast, showToast } = useToast();
  return (
    <>
      <Pressable
        onPress={() =>
          showToast({ title: 'Bybit connected', message: 'Your portfolio is synchronized.', tone: 'success' })
        }>
        <Text>Show</Text>
      </Pressable>
      <Pressable onPress={dismissToast}>
        <Text>Hide</Text>
      </Pressable>
    </>
  );
}

describe('ToastProvider', () => {
  it('announces and dismisses transient feedback without replacing page content', async () => {
    const view = await render(
      <SafeAreaProvider initialMetrics={metrics}>
        <ToastProvider>
          <Harness />
        </ToastProvider>
      </SafeAreaProvider>,
    );

    fireEvent.press(view.getByText('Show'));
    await waitFor(() => expect(view.getByText('Bybit connected')).toBeTruthy());
    expect(view.getByText('Your portfolio is synchronized.')).toBeTruthy();

    fireEvent.press(view.getByText('Hide'));
    await waitFor(() => expect(view.queryByText('Bybit connected')).toBeNull());
  });
});
