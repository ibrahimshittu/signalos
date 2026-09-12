import { describe, expect, it, jest } from '@jest/globals';
import { render } from '@testing-library/react-native';
import { EmptyState } from './States';

describe('EmptyState', () => {
  it('does not repeat a generic status glyph when the caller has no meaningful symbol', async () => {
    const view = await render(
      <EmptyState body="There are no proposals." title="You are up to date" />,
    );

    expect(view.queryByLabelText('checkmark.seal')).toBeNull();
    expect(view.getByText('You are up to date')).toBeTruthy();
  });

  it('keeps user-started empty-state actions visibly busy', async () => {
    const view = await render(
      <EmptyState
        action={{ loading: true, onPress: jest.fn(), title: 'Scan markets' }}
        body="Build the first liquid universe."
        title="Run your first scan"
      />,
    );

    expect(view.getByRole('button').props.accessibilityState).toEqual({
      busy: true,
      disabled: true,
    });
    expect(view.getByRole('button', { name: 'Scan markets' })).toBeOnTheScreen();
    expect(view.getByText('Scan markets')).toBeOnTheScreen();
  });

  it('supports a compact primary action for an in-section empty state', async () => {
    const view = await render(
      <EmptyState
        action={{
          icon: 'arrow.clockwise',
          onPress: jest.fn(),
          title: 'Review markets',
          variant: 'primary',
        }}
        align="center"
        body="No setup has cleared every check."
        density="compact"
        title="No proposals yet"
      />,
    );

    expect(view.getByRole('button', { name: 'Review markets' })).toBeOnTheScreen();
  });
});
