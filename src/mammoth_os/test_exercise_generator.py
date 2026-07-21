from mammoth_os.exercise_generator import generate_exercises_for_lesson


def test_generate_basic_exercise():
    lesson = {
        "title": "Addition Basics",
        "objectives": ["Practice problem: add two numbers"],
    }
    exercises = generate_exercises_for_lesson(lesson, count=1)
    assert isinstance(exercises, list) and len(exercises) == 1
    ex = exercises[0]
    assert 'exercise_id' in ex
    assert 'expected_test' in ex
    assert 'assert' in ex['expected_test']
