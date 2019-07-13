"""This module provides following classes.

1. `State` -> Represents the state.
2. `FiniteStateMachine` -> A finite state machine responsible for state
transition.
3. `TransactionalFiniteStateMachine` -> A finite state machine with the
transaction and conditional rollback support.

"""
import abc
import contextlib
import logging

logger = logging.getLogger(__name__)


class FiniteStateMachineError(Exception):
    """Raised when state machine encounters an error."""


class StateTransitionError(Exception):
    """Raised when state transition encounters an error."""


class InvalidStateError(Exception):
    """Raised when state is found invalid."""


class StateNotFoundError(Exception):
    """Raised when state is not defined before referencing."""


class State:
    """Represents the state.
    """

    def __init__(self, name, initial=False, allowed_transitions=None):
        """Initialize the state.

        :param str name: Name of the state. Case sensitive
        :param bool initial: If True, mark the state as an initial state.
        :param list<State>, list<state_name> allowed_transitions:
            list of other states this state can transition to.
        """
        self._name = name
        self._initial = initial
        self._allowed_transitions = allowed_transitions or []

    @property
    def name(self):
        """Name of the state.

        :return State name
        :rtype: str
        """
        return self._name

    @property
    def allowed_transitions(self):
        """List of allowed transitions.

        :return allowed_transitions list
        :rtype list<State>
        """
        return self._allowed_transitions

    def is_initial(self):
        """Return True if state is initial state, otherwise False

        :return True/False
        :rtype bool
        """
        return self._initial

    def __eq__(self, other):
        """Compare the state with other state by name.
        :param State other: other state object
        :return True if state matches, False otherwise
        :rtype bool
        """
        if type(other) == str:
            return other == self._name
        return other._name == self._name

    def __repr__(self):
        """State representation string.

        :return state information
        :rtype: str
        """
        return "<State name={} initial={}>".format(self._name, self._initial)

    __str__ = __repr__


class Condition(abc.ABC):
    """Abstract condition class that is used to decide if given action
    can be performed or not."""

    @abc.abstractmethod
    def __call__(self):
        """Implement the condition by extending __call__ method.
        subclasses return bool value if condition is matched else
        False.
        """
        raise NotImplementedError()

    def __repr__(self):
        """Condition representation.
        """
        return "<Condition type={}>".format(self.__class__.__name__)


class ExceptionCondition(Condition):
    """Represents the exception condition. This condition can be used to
    perform an action if given exception type matches.
    """

    def __init__(self, exception):
        """
        :param Exception exception: exception object
        """
        self.exception = exception

    def __call__(self, error):
        """Return True if type of the error matches the type of the exception,
        otherwise False.

        :param exception exception: error object
        """
        # return type(error) == type(self.exception())
        return isinstance(error, self.exception)


class Transaction:
    """Represents the transaction. Transaction can be any action whose state
    can be reverted if desired.
    """

    def __init__(
        self,
        target,
        args=None,
        kwargs=None,
        rb_transactions=None,
        rb_conditions=None,
    ):
        """Initialize the transaction.

        :param callable target: Target object
        :param tuple args: Positional arguments to a target
        :param dict kwargs: KeyWord arguments to a target
        :param list<Transaction> rb_transactions: list of transactions
        :param list<Condition> rb_conditions: list of rollback rb_conditions
            to match against the transaction. If these rb_conditions
            are matched, rollback transactions are performed.
        """
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.rb_transactions = rb_transactions or []
        self.rb_conditions = rb_conditions or []
        self._result = None
        self._error = None

    @property
    def error(self):
        """Exception raised during the target execution.

        :return error object
        :rtype: Exception
        """
        return self._error

    @property
    def result(self):
        """Results of the transaction when successful.

        :return target return value
        :rtype: AnyObject
        """
        return self._result

    def __call__(self):
        """Execute the transaction.

        On exception, save the error and perform the rollback transactions.
        On success, save the result.

        :raises Exception occurred during the target execution.
        """
        try:
            result = self.target(*self.args, **self.kwargs)
        except Exception as error:
            logger.exception(error)
            logger.error("Error executing transaction %s", self)

            self._error = error
            # if error occurs, loop through rollback transactions,
            # check if rb_conditions are set or not, execute transactions
            # accordingly.
            logger.info(
                "Running rollback transactions for the transaction %s", self
            )
            for t in self.rb_transactions:
                if self.rb_conditions:
                    for c in self.rb_conditions:
                        if c(error):
                            t()
                            break
                else:
                    t()
            # raise the original exception
            raise
        else:
            logger.info("Saving results for transaction %s", self)
            self._result = result

    def __repr__(self):
        """Transaction representation.
        """
        return "<{} callable={} args={} kwargs={} rb_conditions={}>".format(
            self.__class__.__name__,
            self.target,
            self.args,
            self.kwargs,
            self.rb_conditions,
        )


class FiniteStateMachine:
    """Finite State machine implementation."""

    def __init__(self, name=None, states=None):
        """Initialize the state machine.

        :param str name: optional state machine name
        :param list<State> states: list of states
        """
        self._name = name
        self._states = []
        # set current state to unknown.
        self._current_state = State("UNKNOWN", initial=True)
        self._prev_state = None
        for state in (states or []):
            self.add(state)

    @property
    def name(self):
        """Name of the state machine.

        :return State name
        :rtype: str
        """
        return self._name

    @property
    def current_state(self):
        """Returns the current state.

        :return current state.
        :rtype: State
        """
        return self._current_state

    def add(self, state):
        """Add a new state.

        :param State state: state object
        """
        if not isinstance(state, State):
            raise FiniteStateMachineError(
                "{} state must be an instance of {} class".format(
                    state, State.__name__
                )
            )

        if state.is_initial():
            self._current_state = state
        logger.info("Adding a state %s to a state machine.", state)
        self._states.append(state)

    def _transition(self, new_state):
        """Transition to a give state. If transition is not allowed, raise
        an error.

        :param State new_state: state object
        :raises StateTransitionError: when state transition is not
             allowed.
        """
        logger.info(
            "Checking if state %s is allowed to transition to %s."
            % (self.current_state, new_state)
        )

        if self._is_transition_allowed(self._current_state, new_state):
            logger.info(
                "Transitioning from state %s to %s."
                % (self.current_state, new_state)
            )
            self._prev_state = self._current_state
            self._current_state = new_state
        else:
            logger.error(
                "Transition is not allowed from state %s to %s"
                % (self.current_state, new_state)
            )
            raise StateTransitionError(
                "{} state is not allowed to transition to {}.".format(
                    self._current_state.name, new_state.name
                )
            )

    def _is_transition_allowed(self, from_state, to_state):
        """Returns True if `from_state` is allowed to be transition
        to `to_state`.

        If `to_state` is a next state, allow the transition.

        :param from_state: transition from a state
        :param to_state: transition to a state
        :return True if transition is allowed, False otherwise
        :rtype: bool
        """
        if to_state in from_state.allowed_transitions or \
                self._check_if_next(to_state):
            return True

        return False

    def _check_if_next(self, state):
        """Returns True if state is next state from the current state.

        :param State state: state object
        :return True if given state is the next one, False otherwise
        :rtype: bool
        """
        # is current state is UNKNOWN, check if next state is the first
        # state.
        if self._current_state == State("UNKNOWN"):
            if state in self._states:
                if self._states.index(state) == 0:
                    return True
                else:
                    return False
            else:
                return False

        # if state that is being checked is known to state machine, continue.
        if state in self._states:
            # if current state is not UNKNOWN, check if next state the state
            # being checked.
            if (
                self._states.index(state)
                == self._states.index(self._current_state) + 1
            ):
                return True
            else:
                return False
        else:
            return False

    def transition(self, state):
        """Transition to a next state. If already in that state, return.

        :param State state: state to transition to.
        """
        if self._current_state == state:
            return
        self._transition(state)

    def _revert(self):
        """Revert the state to a previous state."""
        if self._current_state == State("UNKNOWN"):
            return

        index = self._states.index(self._current_state) - 1

        self._current_state = self._prev_state
        self._prev_state = self._states[index]

    def __contains__(self, state):
        """Retruns True if state is part of the state machine.

        :param state: State to be looked upon.
        :return True if state is part of the state machine, False otherwise
        :rtype bool
        """
        return state in self._states

    def __repr__(self):
        """FiniteStateMachine representation.
        """
        return "<{} states={} current_state={}>".format(
            self.__class__.__name__, self._states, self._current_state
        )

    __str__ = __repr__


class TransactionalFiniteStateMachine(FiniteStateMachine):
    """Transactional state machine is responsible for providing the
    concrete implementation to handle the rollback based on the
    specified rb_conditions.
    """

    def __init__(self, name=None, states=None):
        super().__init__(name, states)
        self.transaction_stack = []

    def _revert(self):
        """Override method to revert transactions along with state."""
        super()._revert()
        # until stack is empty, pop the transaction, iterate over the
        # rollback transactions and execute them.
        while self.transaction_stack:
            transaction = self.transaction_stack.pop()
            for rb_transaction in transaction.rb_transactions:
                rb_transaction()

    @contextlib.contextmanager
    def managed_transition(self,
                           state,
                           pre_transactions=None,
                           post_transactions=None,
                           on_error_transactions=None):
        """Transition to the give state with transactions. Revert the state
        in case of.

        :param sequence<Transaction> pre_transactions: transactions to
                perform before the state is transitioned to the next.
        :param sequence<Transaction> post_transactions: transactions to
                perform if no exceptions occur.
        :param sequence<Transaction> on_error_transactions: transactions to
                perform if errors occur.

        :return yield the state machine object
        :rtype: TransactionalFiniteStateMachine

        :raises FiniteStateMachineError
        :raises StateTransitionError
        :raises Exception
        """
        pre_transactions = pre_transactions or []
        post_transactions = post_transactions or []
        on_error_transactions = on_error_transactions or []

        # Transition to a given state first. Only proceed if state transition
        # is allowed.
        # Raises FiniteStateMachineError or StateTransitionError error.
        self.transition(state)

        # Execute transactions before changing the state.
        # revert the transactions if rollbacks are set.
        # raise the exception captured and exit the state
        # machine.
        logger.info("Executing set of pre transactions if set.")

        try:
            for transaction in pre_transactions:
                transaction()
                self.transaction_stack.append(transaction)
        except Exception:
            self._revert()
            raise

        # If no exceptions occurred, allow users to perform
        # actions defined in in `with` block.
        try:
            yield
        # If exceptions occur in `with` block, do not transition
        # to next state, and execute transactions defined in
        # `on_exception` sequence.
        except Exception:
            self._revert()
            logger.info("Executing set of on_exception transactions if set.")
            try:
                for transaction in on_error_transactions:
                    transaction()
            # If there are exceptions executing the `on_exception`
            # transactions, revert things by calling rollbacks defined
            # on those transactions and raising the original exception.
            except Exception:
                raise
            # If there are no exceptions executing the `on_exception`,
            # raise the exception occurred in `with` block.
            raise

        # If no exceptions occurred in `with` block, execute the `after`
        # transactions. If case of the exception during executing the
        # `after` exceptions, revert things by calling rollbacks defined
        # on those transactions and raising the original exception.
        else:

            logger.info("Executing set of post transactions if set.")
            try:
                for transaction in post_transactions:
                    transaction()
                    self.transaction_stack.append(transaction)
            except Exception:
                self._revert()
                raise

    def __repr__(self):
        """Transactional State Machine representation.
        :return state machine information.
        :rtype: string
        """
        return "<{} State={}>".format(
            self.__class__.__name__, self._current_state.name
        )


if __name__ == "__main__":
    pass
    # def _fetch_policy_details():
    #     print("fetching policy details.")
    #     return "adfasdafd"

    # def _activate_policy():
    #     print("activating policy.")

    # def _deactivate_policy():
    #     print("deactivating policy.")

    # def _revert_policy():
    #     print("reverting policy.")

    # def _poll_activation_status():
    #     print("polling activation status.")

    # def _update_migration_event():
    #     print("updating migration event.")

    # QUEUED = State("QUEUED", allowed_transitions=["SUCCESSFUL", "FAILED"])
    # POSTED = State("POSTED", allowed_transitions=["ACTIVE", "FAILED"])
    # ACTIVE = State("ACTIVE", allowed_transitions=["SUCCESSFUL", "FAILED"])
    # SUCCESSFUL = State("SUCCESSFUL")
    # FAILED = State("FAILED")

    # tsm = TransactionalFiniteStateMachine()

    # tsm.add(QUEUED)
    # tsm.add(POSTED)
    # tsm.add(ACTIVE)
    # tsm.add(SUCCESSFUL)
    # tsm.add(FAILED)
    # t = Transaction(
    #     _fetch_policy_details,
    #     rb_transactions=[Transaction(_revert_policy)],
    #     rb_conditions=[ExceptionCondition(Exception)],
    # )
    # with tsm.managed_transition(
    #     state=QUEUED,
    #     pre_transactions=[t, Transaction(_update_migration_event)],
    #     on_error_transactions=[Transaction(_deactivate_policy)],
    #     post_transactions=[Transaction(_poll_activation_status)],
    # ):
    #     a = _activate_policy()

    # with tsm.managed_transition(
    #     state=ACTIVE,
    #     pre_transactions=[t, Transaction(_update_migration_event)],
    #     on_error_transactions=[Transaction(_deactivate_policy)],
    #     post_transactions=[Transaction(_poll_activation_status)],
    # ):
    #     a = _activate_policy()

    # class LightController:
    #     def turn_off_light(self, room):
    #         print('turning the {} room light off.'.format(room))

    #     def turn_on_light(self, room):
    #         print('turning the {} room light on.'.format(room))

    # light_controller = LightController()

    # def turn_off_water():
    #     print('turning off the water.')

    # def turn_on_water():
    #     print('turning on the water.')

    # def water_plants():
    #     print('watering the plants.')

    # def lock_the_door():
    #     print('locking the door.')

    # def unlock_the_door():
    #     print('unlocking the door.')

    # UNLOCKED = State(
    # 'UNLOCKED', initial=True, allowed_transitions=['LOCKED'])
    # LOCKED = State('LOCKED', initial=False, allowed_transitions=['UNLOCKED'])

    # tsm = TransactionalFiniteStateMachine(name='Lock')
    # tsm.add(LOCKED)
    # tsm.add(UNLOCKED)

    # light_transaction = Transaction(
    #     target=light_controller.turn_off_light,
    #     args=('Living',),
    #     rb_transactions=[
    #         Transaction(target=light_controller.turn_on_light,
    #                     args=('Living',))
    #     ])

    # water_transaction = Transaction(
    #     target=turn_off_water,
    #     rb_transactions=[
    #         Transaction(target=turn_on_water)
    #     ]
    # )

    # with tsm.managed_transition(
    #         state=LOCKED,
    #         pre_transactions=[light_transaction, water_transaction],
    #         on_error_transactions=[Transaction(unlock_the_door)],
    #         post_transactions=[Transaction(water_plants)]):
    #     lock_the_door()

    # print(tsm.current_state)
