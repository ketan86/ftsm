# Finite Transactional State Machine 
Finite Transactional State Machine is a Transaction driven finite state machine. 
Transaction can be any Python callable object that is reverted when exceptions 
occur.

## Installation 
`pip3 install ftsm`


## How does it work ?

1. Create states and list of possible transitions the state is allowed 
to transition to.
    ```python
    UNLOCKED = State('UNLOCKED', initial=True, allowed_transitions=['LOCKED'])
    LOCKED = State('LOCKED', initial=False, allowed_transitions=['UNLOCKED'])
    ```
2. Initialize the transitional state machine.
    ```python
    tsm = TransactionalFiniteStateMachine(name='Lock')
    ```
3. Add defined states to a state machine.
    ```python
    tsm.add(LOCKED)
    tsm.add(UNLOCKED)
    ```
4. Create transaction and define rollback transactions with or without conditions.
    ```python
    t1 = Transaction(
    target=func,
    args=('name',),
    rb_transactions=[t2],
    rb_conditions=[ExceptionCondition(KeyError)])
    ```
5. Transition to a new state with transactions.
    ```python
    with tsm.managed_transition(
            state=LOCKED,
            pre_transactions=[t1, t3],
            on_error_transactions=[t4],
            post_transactions=[t5]):
        func()
    ```
## Example 

```python
from ftsm import State, Transaction, TransactionalFiniteStateMachine

class LightController:
    def turn_off_light(self, room):
        print('turning the {} room light off.'.format(room))

    def turn_on_light(self, room):
        print('turning the {} room light on.'.format(room))

light_controller = LightController()

def turn_off_water():
    print('turning off the water.')

def turn_on_water():
    print('turning on the water.')

def water_plants():
    print('watering the plants.')

def lock_the_door():
    print('locking the door.')

def unlock_the_door():
    print('unlocking the door.')

UNLOCKED = State('UNLOCKED', initial=True, allowed_transitions=['LOCKED'])
LOCKED = State('LOCKED', initial=False, allowed_transitions=['UNLOCKED'])

tsm = TransactionalFiniteStateMachine(name='Lock')
tsm.add(LOCKED)
tsm.add(UNLOCKED)

light_transaction = Transaction(
    target=light_controller.turn_off_light,
    args=('Living',),
    rb_transactions=[
        Transaction(target=light_controller.turn_on_light,
                    args=('Living',))
    ])

water_transaction = Transaction(
    target=turn_off_water,
    rb_transactions=[
        Transaction(target=turn_on_water)
    ]
)

with tsm.managed_transition(
        state=LOCKED,
        pre_transactions=[light_transaction, water_transaction],
        on_error_transactions=[Transaction(unlock_the_door)],
        post_transactions=[Transaction(water_plants)]):
    lock_the_door()

print(tsm.current_state)
```

Above sample code would result in following output. 
```python
turning the Living room light off.
turning off the water.
locking the door.
watering the plants.
<State name=LOCKED initial=False>
```

If errors occur while performing the transactions, revert transactions are performed 
in the reverse order and state transition does not happens.

Rollback transaction can also be made conditional using the `ExceptionCondition`
class provided. 

```
light_transaction = Transaction(
    target=light_controller.turn_off_light,
    args=('Living',),
    rb_transactions=[
        Transaction(target=light_controller.turn_on_light,
                    args=('Living',))
    ],
    rb_conditions=[ExceptionCondition(KeyError)])
```
Above transaction now only be reverted if KeyError is encountered during the
transaction execution. 

User can extend the abstract `Condition` class to defined new Condition.