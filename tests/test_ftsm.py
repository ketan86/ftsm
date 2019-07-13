import logging
import unittest
from unittest.mock import patch, MagicMock, ANY, DEFAULT

from ftsm.ftsm import (State, Condition,
                       ExceptionCondition,
                       FiniteStateMachine,
                       TransactionalFiniteStateMachine,
                       StateTransitionError,
                       FiniteStateMachineError,
                       Transaction)


logging.disable(logging.ERROR)


class TestFiniteStateMachine(unittest.TestCase):
    """Test the state machine."""

    def test_state_equality_by_name(self):
        state = State('TEST', allowed_transitions=[State('UNKOWN')])
        self.assertEqual(state,
                         State('TEST', allowed_transitions=[
                             State('TEST_UNKNOWN')]))

    def test_state_name_getter(self):
        state = State('Locked')
        self.assertEqual('Locked', state.name)

    def test_state_repr(self):
        state = State('TEST')
        self.assertEqual(repr(state),
                         '<State name=TEST initial=False>')

    def test_state_initial_true(self):
        state = State('TEST', initial=True)
        self.assertEqual(state.is_initial(),
                         True)

    def test_state_initial_false(self):
        state = State('TEST')
        self.assertEqual(state.is_initial(),
                         False)

    def test_allowed_transitions(self):
        state = State('TEST', allowed_transitions=[State('UNKOWN')])
        self.assertEqual(state.allowed_transitions,
                         [State('UNKOWN')])

    def test_condition_abstract_method(self):

        class TestSubCondition(Condition):

            def __init__(self):
                pass
        with self.assertRaisesRegex(
                TypeError,
                'Can\'t instantiate abstract class TestSubCondition with '
                'abstract methods __call__'):
            tc = TestSubCondition()

    def test_exception_condition_call_method_positive(self):

        ec = ExceptionCondition(TypeError)
        result = ec(TypeError())
        self.assertEqual(result,
                         True)

    def test_exception_condition_call_method_negative(self):

        ec = ExceptionCondition(TypeError)
        result = ec(KeyError())
        self.assertEqual(result,
                         False)

    def test_transaction_no_rb(self):
        callable_func_mock = MagicMock()
        rb_callable_func_mock = MagicMock()

        t = Transaction(target=callable_func_mock,
                        rb_transactions=[
                            Transaction(target=rb_callable_func_mock)])
        t()
        callable_func_mock.assert_called_once()
        rb_callable_func_mock.assert_not_called()

    def test_transaction_no_rb_result(self):
        callable_func_mock = MagicMock()
        callable_func_mock.return_value = 'func_return'
        rb_callable_func_mock = MagicMock()

        t = Transaction(target=callable_func_mock,
                        rb_transactions=[
                            Transaction(target=rb_callable_func_mock)])
        t()
        callable_func_mock.assert_called_once()
        rb_callable_func_mock.assert_not_called()
        self.assertEqual(t.result, 'func_return')
        self.assertEqual(t.error, None)

    def test_transaction_rb(self):
        callable_func_mock = MagicMock()
        callable_func_mock.side_effect = Exception('Failed')
        rb_callable_func_mock = MagicMock()

        t = Transaction(target=callable_func_mock,
                        rb_transactions=[
                            Transaction(target=rb_callable_func_mock)])
        with self.assertRaisesRegex(Exception, 'Failed'):
            t()
        callable_func_mock.assert_called_once()
        rb_callable_func_mock.assert_called_once()

        self.assertEqual(t.result, None)
        self.assertEqual(type(t.error), type(Exception('Failed')))

    def test_transaction_rb_order(self):
        callable_func_mock = MagicMock()
        callable_func_mock.side_effect = Exception('Failed')
        rb_callable_func_mock = MagicMock()
        rb_callable_func_2_mock = MagicMock()

        t = Transaction(target=callable_func_mock,
                        rb_transactions=[
                            Transaction(target=rb_callable_func_mock),
                            Transaction(target=rb_callable_func_2_mock)])
        with self.assertRaisesRegex(Exception, 'Failed'):
            t()
        callable_func_mock.assert_called_once()
        rb_callable_func_mock.assert_called_once()
        rb_callable_func_2_mock.assert_called_once()

        self.assertEqual(t.result, None)
        self.assertEqual(type(t.error), type(Exception('Failed')))

    def test_transaction_rb_with_condition_matched(self):
        callable_func_mock = MagicMock()
        callable_func_mock.side_effect = Exception('Failed')
        rb_callable_func_mock = MagicMock()

        t = Transaction(target=callable_func_mock,
                        rb_transactions=[
                            Transaction(
                                target=rb_callable_func_mock,
                                rb_conditions=[ExceptionCondition(Exception)])])
        with self.assertRaisesRegex(Exception, 'Failed'):
            t()
        callable_func_mock.assert_called_once()
        rb_callable_func_mock.assert_called_once()
        self.assertEqual(t.result, None)
        self.assertEqual(type(t.error), type(Exception('Failed')))

    def test_transaction_rb_with_condition_not_matched(self):
        callable_func_mock = MagicMock()
        callable_func_mock.side_effect = Exception('Failed')
        rb_callable_func_mock = MagicMock()

        t = Transaction(target=callable_func_mock,
                        rb_transactions=[Transaction(
                            target=rb_callable_func_mock)
                        ],
                        rb_conditions=[ExceptionCondition(TypeError)])
        with self.assertRaisesRegex(Exception, 'Failed'):
            t()
        callable_func_mock.assert_called_once()
        rb_callable_func_mock.assert_not_called()
        self.assertEqual(t.result, None)
        self.assertEqual(type(t.error), type(Exception('Failed')))

    def test_transaction_repr(self):
        callable_func_mock = MagicMock()
        rb_callable_func_mock = MagicMock()

        t = Transaction(target=callable_func_mock,
                        rb_transactions=[
                            Transaction(target=rb_callable_func_mock)])
        t()

        self.assertEqual(str(t),
                         '<Transaction callable={} args={} kwargs={} rb_conditions={}>'
                         .format(callable_func_mock, (), {}, []))

    def test_state_machine_init(self):
        states = [State('1'), State('2'), State('3')]
        sm = FiniteStateMachine(states)

        self.assertEqual(sm.current_state,
                         State('UNKNOWN'))
        self.assertEqual(sm._prev_state,
                         None)
        self.assertEqual(sm._states,
                         states)

    def test_state_machine_transition(self):
        states = [State('1'), State('2'), State('3')]
        sm = FiniteStateMachine(states)
        sm.transition(states[0])
        self.assertEqual(sm.current_state, states[0])

    def test_state_machine_transition_revert(self):
        states = [State('1'), State('2'), State('3')]
        sm = FiniteStateMachine(states)
        sm.transition(states[0])
        sm._revert()
        self.assertEqual(sm.current_state, State('UNKNOWN'))

    def test_state_machine_add_exception(self):
        sm = FiniteStateMachine()
        with self.assertRaisesRegex(
                FiniteStateMachineError,
                'TEST state must be an instance of State class'):
            sm.add('TEST')

    def test_state_machine_repr_unknown(self):
        sm = FiniteStateMachine()

        self.assertEqual(
            str(sm),
            '<FiniteStateMachine states=[] current_state=<State name=UNKNOWN initial=True>>')

    def test_state_machine_repr(self):
        sm = FiniteStateMachine(
            [State('1', initial=True), State('2'), State('3')])

        self.assertEqual(
            str(sm),
            '<FiniteStateMachine states=[<State name=1 initial=True>, <State name=2 initial=False>, '
            '<State name=3 initial=False>] current_state=<State name=1 initial=True>>')

    def test_tsm_before_transactions_positive(self):
        callable_func_mock = MagicMock()
        states = [State('1'), State('2'), State('3')]
        sm = TransactionalFiniteStateMachine(states)
        with sm.managed_transition(states[0],
                                   pre_transactions=[Transaction(
                                       target=callable_func_mock,
                                       args=(1, 2),
                                       kwargs={'test': 'hi'})]):
            pass

        self.assertEqual(sm.current_state, states[0])
        callable_func_mock.assert_called_once_with(1, 2, test='hi')

    def test_tsm_before_transactions_negative(self):
        callable_func_mock = MagicMock()
        callable_func_2_mock = MagicMock()
        callable_func_mock.side_effect = Exception('Failed')
        states = [State('1', initial=True, allowed_transitions=['2']),
                  State('2'), State('3')]
        sm = TransactionalFiniteStateMachine(states)
        with self.assertRaisesRegex(
                Exception, 'Failed'):
            with sm.managed_transition(states[1],
                                       pre_transactions=[Transaction(
                                           target=callable_func_mock,
                                           args=(1, 2),
                                           kwargs={'test': 'hi'}),
                                       Transaction(
                                           target=callable_func_2_mock,
                                           args=(4, 5),
                                           kwargs={'test': 'hello'})]):
                pass
        self.assertEqual(sm.current_state, State('1'))

        callable_func_mock.assert_called_once_with(1, 2, test='hi')
        callable_func_2_mock.assert_not_called()

    def test_tsm_on_exception_transactions(self):
        callable_func_mock = MagicMock()
        callable_func_mock.side_effect = Exception(
            'On Exceptions Rollback Error.')
        callable_func_2_mock = MagicMock()
        states = [State('1'), State('2'), State('3')]
        sm = TransactionalFiniteStateMachine(states)
        with self.assertRaisesRegex(
                Exception, 'On Exceptions Rollback Error.'):
            with sm.managed_transition(states[0],
                                       on_error_transactions=[Transaction(
                                           target=callable_func_mock,
                                           args=(1, 2),
                                           kwargs={'test': 'hi'},
                                           rb_transactions=[Transaction(
                                               target=callable_func_2_mock,
                                               args=(4, 5),
                                               kwargs={'test': 'hello'})])]):
                raise Exception('Error during transition')

        self.assertEqual(sm.current_state, State('UNKNOWN'))
        callable_func_mock.assert_called_once_with(1, 2, test='hi')
        callable_func_2_mock.assert_called_once_with(4, 5, test='hello')

    def test_tsm_with_context_error(self):
        callable_func_mock = MagicMock()
        callable_func_mock.side_effect = Exception(
            'On Exceptions Rollback Error.')
        states = [State('1'), State('2'), State('3')]
        sm = TransactionalFiniteStateMachine(states)
        with self.assertRaisesRegex(
                Exception, 'Error during transition'):
            with sm.managed_transition(states[0]):
                raise Exception('Error during transition')

        self.assertEqual(sm.current_state, State('UNKNOWN'))

    def test_tsm_after_transactions(self):
        callable_func_mock = MagicMock()
        callable_func_mock.side_effect = Exception(
            'On Exceptions Rollback Error.')
        callable_func_2_mock = MagicMock()
        states = [State('1'), State('2', initial=True), State('3')]
        sm = TransactionalFiniteStateMachine(states)
        with self.assertRaisesRegex(
                Exception, 'On Exceptions Rollback Error.'):
            with sm.managed_transition(states[2],
                                       pre_transactions=[Transaction(
                                           target=callable_func_mock,
                                           args=(1, 2),
                                           kwargs={'test': 'hi'},
                                           rb_transactions=[Transaction(
                                               target=callable_func_2_mock,
                                               args=(4, 5),
                                               kwargs={'test': 'hello'})])]):
                pass

        self.assertEqual(sm.current_state, states[1])
        callable_func_mock.assert_called_once_with(1, 2, test='hi')
        callable_func_2_mock.assert_called_once_with(4, 5, test='hello')
