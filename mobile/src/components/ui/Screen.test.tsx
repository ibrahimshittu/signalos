import { describe, expect, it } from '@jest/globals';
import { render } from '@testing-library/react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { FlowScreen, Screen } from './Screen';
import { Text } from './Text';

const metrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, right: 0, bottom: 34, left: 0 },
};

describe('screen keyboard behavior', () => {
  it('keeps a flow footer above the keyboard and adjusts the scroll inset', async () => {
    const view = await render(
      <SafeAreaProvider initialMetrics={metrics}>
        <FlowScreen footer={<Text>Continue</Text>}>
          <Text>Form</Text>
        </FlowScreen>
      </SafeAreaProvider>,
    );

    const adjustedScrolls = view.container.queryAll(
      (node) => node.props.automaticallyAdjustKeyboardInsets === true,
    );

    expect(adjustedScrolls).toHaveLength(1);
    expect(adjustedScrolls[0].props.keyboardDismissMode).toBe('interactive');
  });

  it('adjusts a standard scrolling screen around focused fields', async () => {
    const view = await render(
      <Screen>
        <Text>Form</Text>
      </Screen>,
    );

    expect(
      view.container.queryAll((node) => node.props.automaticallyAdjustKeyboardInsets === true),
    ).toHaveLength(1);
  });
});
