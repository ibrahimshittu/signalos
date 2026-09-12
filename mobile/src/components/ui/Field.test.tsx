import { describe, expect, it } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';
import { Field } from './Field';
import { tokens } from '@/theme/tokens';

describe('Field', () => {
  it('centers single-line input text within the control', async () => {
    const view = await render(
      <Field label="Capital" onChangeText={() => undefined} prefix="$" value="5,000" />,
    );

    const input = view.getByLabelText('Capital');
    const prefix = view.getByText('$');
    const style = StyleSheet.flatten(input.props.style);
    const prefixStyle = StyleSheet.flatten(prefix.props.style);

    expect(input.props.multiline).toBe(false);
    expect(style.height).toBeGreaterThanOrEqual(tokens.layout.control - 2);
    expect(style.paddingVertical).toBe(0);
    expect(style.textAlignVertical).toBe('center');
    expect(style.lineHeight).toBeUndefined();
    expect(style.transform).toBeUndefined();
    expect(prefixStyle.transform).toBeUndefined();
  });

  it('reveals a secret only on request and hides it again when the field loses focus', async () => {
    const view = await render(
      <Field label="Password" onChangeText={() => undefined} secureTextEntry value="test-secret" />,
    );
    expect(view.getByLabelText('Password').props.secureTextEntry).toBe(true);
    await fireEvent.press(view.getByRole('button', { name: 'Show Password' }));
    expect(view.getByLabelText('Password').props.secureTextEntry).toBe(false);
    expect(view.getByLabelText('Password').props.value).toBe('test-secret');
    await fireEvent(view.getByLabelText('Password'), 'blur');
    expect(view.getByLabelText('Password').props.secureTextEntry).toBe(true);
  });
});
