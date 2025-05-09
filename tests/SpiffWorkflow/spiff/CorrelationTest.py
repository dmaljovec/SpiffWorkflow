from SpiffWorkflow.bpmn import BpmnWorkflow, BpmnEvent
from SpiffWorkflow import TaskState

from .BaseTestCase import BaseTestCase

class CorrelationTest(BaseTestCase):

    def testMessagePayload(self):
        self.actual_test(False)

    def testMessagePayloadSaveRestore(self):
        self.actual_test(True)

    def actual_test(self,save_restore):

        specs = self.get_all_specs('correlation.bpmn')
        proc_1 = specs['proc_1']
        self.workflow = BpmnWorkflow(proc_1, specs)
        if save_restore:
            self.save_restore()
        self.workflow.do_engine_steps()
        # Set up some data to evaluate the payload expression against
        for idx, task in enumerate(self.get_ready_user_tasks()):
            task.data['task_num'] = idx
            task.data['task_name'] = f'subprocess {idx}'
            task.data['extra_data'] = 'unused data'
            task.run()
        self.workflow.do_engine_steps()
        ready_tasks = self.get_ready_user_tasks()
        for task in ready_tasks:
            self.assertEqual(task.task_spec.name, 'prepare_response')
            response = 'OK' if task.data['source_task']['num'] else 'No'
            task.data.update(response=response)
            task.run()
        self.workflow.do_engine_steps()
        # If the messages were routed properly, the task number should match the response id
        for task in self.workflow.get_tasks(spec_name='subprocess_end'):
            self.assertEqual(task.data['response']['init_id'], task.data['task_num'])
            self.assertEqual(task.data['response']['response'], 'OK' if task.data['task_num'] else 'No')


class DualConversationTest(BaseTestCase):

    def testTwoCorrelatonKeys(self):

        spec, subprocesses = self.load_workflow_spec('correlation_two_conversations.bpmn', 'message_send_process')
        workflow = BpmnWorkflow(spec, subprocesses)
        workflow.do_engine_steps()
        messages = workflow.get_events()
        self.assertEqual(len(messages), 2)
        self.assertEqual('Message Send One', messages[0].event_definition.name)
        self.assertEqual('Message Send Two', messages[1].event_definition.name)
        self.assertIn('message_correlation_key_one', messages[0].correlations)
        self.assertNotIn('message_correlation_key_one', messages[1].correlations)
        self.assertIn('message_correlation_key_two', messages[1].correlations)
        self.assertNotIn('message_correlation_key_two', messages[0].correlations)


class ReceiveCorrelationTest(BaseTestCase):

    def testReceiveCorrelations(self):
        self.actual_test()

    def testReceiveCorrelationsSaveRestore(self):
        self.actual_test(True)

    def actual_test(self, save_restore=False):
        spec, subprocesses = self.load_workflow_spec('receive_correlations.bpmn', 'correlation-test')
        self.workflow = BpmnWorkflow(spec, subprocesses)
        if save_restore:
            self.save_restore()
        self.workflow.do_engine_steps()
        task = self.workflow.get_next_task(state=TaskState.READY)
        task.data.update(value_1='a', value_2='b')
        task.run()
        self.workflow.do_engine_steps()
        self.assertEqual(self.workflow.correlations, {'test': {'prop_1': 'a', 'prop_2': 'b'}})
        waiting_task = self.workflow.get_next_task(state=TaskState.WAITING)
        event_def = waiting_task.task_spec.event_definition
        payload = {'msg_value_1': 'a', 'msg_value_2': 'b'}
        correlations = event_def.calculate_correlations(
            waiting_task.workflow.script_engine,
            event_def.correlation_properties,
            payload
        )
        event = BpmnEvent(event_def, payload, correlations)
        self.workflow.catch(event)
        self.workflow.do_engine_steps()
        self.assertTrue(self.workflow.completed)

class DefaultCorrelationKeyTest(BaseTestCase):

    def test_default_key(self):
        spec, subprocesses = self.load_workflow_spec('default_correlation_key.bpmn', 'main')
        self.workflow = BpmnWorkflow(spec, subprocesses)
        self.workflow.do_engine_steps()
        self.assertEqual(self.workflow.correlations, {'MainCorrelationKey': {'uid': 1}})
        waiting_task = self.workflow.get_next_task(state=TaskState.WAITING)
        event_def = waiting_task.task_spec.event_definition
        payload = {'uid': 1}
        correlations = event_def.calculate_correlations(
            waiting_task.workflow.script_engine,
            event_def.correlation_properties,
            payload
        )
        event = BpmnEvent(event_def, payload, correlations)
        self.workflow.catch(event)
        self.workflow.do_engine_steps()
        self.assertTrue(self.workflow.completed)

