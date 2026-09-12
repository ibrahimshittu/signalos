import { useState } from 'react';
import {
  StyleSheet,
  TextInput,
  View,
  useWindowDimensions,
  type TextInputProps,
} from 'react-native';
import { Glyph } from './Glyph';
import { Touchable } from './Touchable';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

type Props = Pick<
  TextInputProps,
  | 'autoCapitalize'
  | 'autoComplete'
  | 'autoFocus'
  | 'keyboardType'
  | 'maxLength'
  | 'secureTextEntry'
  | 'textContentType'
  | 'returnKeyType'
  | 'onSubmitEditing'
> & {
  label: string;
  value: string;
  onChangeText(value: string): void;
  placeholder?: string;
  /** Static guidance. Replaced by `error` when validation fails. */
  hint?: string;
  error?: string;
  /** Renders the value in tabular figures — use for money and codes. */
  numeric?: boolean;
  prefix?: string;
};

/**
 * A labelled text input.
 *
 * Focus adds a soft ring rather than thickening the border, so nothing shifts
 * by half a pixel as the user moves between fields. An error always adds a
 * written message that is announced — the red border is never the only signal.
 */
export function Field({
  error,
  hint,
  label,
  numeric = false,
  onChangeText,
  placeholder,
  prefix,
  secureTextEntry,
  value,
  ...input
}: Props) {
  const [focused, setFocused] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const { fontScale } = useWindowDimensions();
  const inputHeight = Math.max(
    tokens.layout.control - 2,
    Math.ceil(tokens.type.body.fontSize * Math.min(fontScale, tokens.maxFontSizeMultiplier) * 1.4) +
      tokens.space.base,
  );

  return (
    <View style={styles.field}>
      <Text tone="secondary" variant="subhead">
        {label}
      </Text>

      <View style={[styles.box, focused && styles.focused, error ? styles.errored : null]}>
        {prefix ? (
          <Text numeric tone="secondary" variant="body">
            {prefix}
          </Text>
        ) : null}
        <TextInput
          {...input}
          autoCorrect={false}
          accessibilityHint={error ?? hint}
          accessibilityLabel={label}
          maxFontSizeMultiplier={tokens.maxFontSizeMultiplier}
          multiline={false}
          onBlur={() => {
            setFocused(false);
            setRevealed(false);
          }}
          onChangeText={onChangeText}
          onFocus={() => setFocused(true)}
          placeholder={placeholder}
          placeholderTextColor={tokens.color.text.tertiary}
          selectionColor={tokens.color.accent.base}
          secureTextEntry={secureTextEntry && !revealed}
          style={[styles.input, { height: inputHeight }, numeric && tokens.tabular]}
          value={value}
        />
        {secureTextEntry ? (
          <Touchable
            accessibilityLabel={`${revealed ? 'Hide' : 'Show'} ${label}`}
            accessibilityRole="button"
            accessibilityState={{ selected: revealed }}
            feedback="opacity"
            onPress={() => setRevealed((current) => !current)}
            style={styles.visibility}
          >
            <Glyph name={revealed ? 'eye.slash' : 'eye'} size={19} />
          </Touchable>
        ) : null}
      </View>

      {error ? (
        <Text
          accessibilityLiveRegion="polite"
          accessibilityRole="alert"
          tone="loss"
          variant="footnote"
        >
          {error}
        </Text>
      ) : hint ? (
        <Text tone="tertiary" variant="footnote">
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: tokens.space.sm },
  box: {
    minHeight: tokens.layout.control,
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.xs,
    paddingHorizontal: tokens.space.base,
    borderRadius: tokens.radius.md,
    borderCurve: 'continuous',
    borderWidth: 1,
    borderColor: tokens.color.border.strong,
    backgroundColor: tokens.color.bg.surface,
  },
  focused: {
    borderColor: tokens.color.accent.base,
    boxShadow: '0 0 0 3px rgba(26,78,138,0.12)',
  },
  errored: {
    borderColor: tokens.color.finance.loss,
    boxShadow: '0 0 0 3px rgba(179,37,28,0.10)',
  },
  input: {
    flex: 1,
    paddingVertical: 0,
    textAlignVertical: 'center',
    includeFontPadding: false,
    color: tokens.color.text.primary,
    fontSize: tokens.type.body.fontSize,
    fontWeight: tokens.type.body.fontWeight,
  },
  visibility: {
    minWidth: tokens.layout.touch,
    minHeight: tokens.layout.touch,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: -tokens.space.sm,
  },
});
