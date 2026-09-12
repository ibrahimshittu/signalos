import { describe, expect, it, jest } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';
import { MarketReviewList } from './MarketReviewList';

describe('MarketReviewList', () => {
  it('shows the reviewed stage and its reason without presenting a proposal', async () => {
    const openReview = jest.fn();
    const view = await render(
      <MarketReviewList
        candidates={[
          {
            category: 'linear',
            symbol: 'BTCUSDT',
            rank: 1,
            status: 'no_approved_strategy',
            reason: 'No live strategy is available for trade analysis.',
            strategy_id: null,
          },
        ]}
        approvedStrategyCount={0}
        onOpenReview={openReview}
      />,
    );

    expect(view.getByText('Screened')).toBeOnTheScreen();
    expect(
      view.queryByText('No live strategy is available for trade analysis.'),
    ).not.toBeOnTheScreen();
    expect(view.queryByText('Proposal')).not.toBeOnTheScreen();

    fireEvent.press(view.getByRole('button', { name: /open BTC\/USDT review details/i }));
    expect(openReview).toHaveBeenCalledWith(
      expect.objectContaining({ category: 'linear', symbol: 'BTCUSDT' }),
    );
  });
});
