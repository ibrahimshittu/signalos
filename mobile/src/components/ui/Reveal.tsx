import { type PropsWithChildren } from 'react';
import Animated, { Easing, FadeIn, FadeInDown, useReducedMotion } from 'react-native-reanimated';
import { tokens } from '@/theme/tokens';

interface Props {
  /** Position in the group. Multiplied by the stagger step, capped at 6. */
  index?: number;
}

/**
 * A first-render entrance, staggered across siblings.
 *
 * It runs once, on mount, and only on screens the user arrives at — never on
 * list rows, which would re-animate on every scroll recycle. Under Reduce
 * Motion the movement drops and only the fade remains, which still explains
 * that content arrived without moving the viewport.
 */
export function Reveal({ children, index = 0 }: PropsWithChildren<Props>) {
  const reduceMotion = useReducedMotion();
  const delay = Math.min(index, 6) * tokens.motion.duration.stagger;

  const entering = reduceMotion
    ? FadeIn.duration(tokens.motion.duration.state)
    : FadeInDown.duration(tokens.motion.duration.enter)
        .delay(delay)
        .withInitialValues({ transform: [{ translateY: tokens.motion.enterOffset }] })
        .easing(Easing.bezier(...tokens.motion.easing.out));

  return <Animated.View entering={entering}>{children}</Animated.View>;
}
