package bond;

import java.util.*;

/**
 * Class used to represent an observation. An observation is built up as a collection
 * of (key, value) pairs using a builder-style pattern. For more information, see the
 * class description for {@link Bond}.
 */
public class Observation {

  /**
   * Package-private to make sure this only gets instantiated through
   * {@link Bond#obs(String, Object)}
   */
  Observation() {

  }

  // Sorted map, forcing __spyPoint__ to appear as the first entry (if present)
  private SortedMap<String, Object> _observationMap = new TreeMap<>(new Comparator<String>() {
    @Override
    public int compare(String s1, String s2) {
      if (s1.equals("__spyPoint__")) {
        return -1;
      } else if (s2.equals("__spyPoint__")) {
        return 1;
      } else {
        return s1.compareTo(s2);
      }
    }
  });

  /**
   * Add a (key, value) pair to the current observation.
   *
   * @see Bond#obs(String, Object)
   * @param key Name of the value being observed
   * @param value Value to be observed
   * @return This object to continue to be used in a builder-style pattern
   */
  public Observation obs(String key, Object value) {
    _observationMap.put(key, value);
    return this;
  }

  /**
   * Spies with the currently built observation and an anonymous spy point.
   *
   * @see Bond#spy()
   */
  public void spy() {
    spy(null);
  }

  /**
   * Spies with the currently built observation.
   *
   * @see Bond#spy(String)
   * @param spyPointName Name of the point being spied on.
   * @return The result of the agent deployed for this point, if any,
   *         else an absent {@link SpyResult}.
   */
  public SpyResult<Object> spy(String spyPointName) {
    if (!Bond.isActive()) {
      return SpyResult.absent();
    }
    SpyAgent agent = Bond.getAgent(spyPointName, _observationMap);
    processObservation(spyPointName);
    if (agent != null) {
      return agent.performDoersGetReturn(_observationMap);
    } else {
      return SpyResult.absent();
    }
  }

  /**
   * Spies this point with the current observation, expecting a return type of
   * {@code expectedType}. Has no effect and returns an absent {@link SpyResult}
   * if {@link Bond#isActive()} is false.
   *
   * @see Bond#spy(String, Class)
   * @param spyPointName Name of the point being spied on
   * @param expectedType Type of value expected to be returned from any active {@link SpyAgent}
   * @param <T> Same as expectedType
   * @throws IllegalSpyAgentException If the result from the agent matching
   *         this spy point does not match expectedType.
   * @return The result of the agent deployed for this point, if any,
   *         else an absent {@link SpyResult}.
   */
  public <T> SpyResult<T> spy(String spyPointName, Class<T> expectedType) {
    if (!Bond.isActive()) {
      return SpyResult.absent();
    }
    SpyResult<T> ret = (SpyResult<T>) spy(spyPointName);
    if (ret.isPresent()) {
      if (!isTypeCompatible(ret.get(), expectedType)) {
        throw new IllegalSpyAgentException("Requested a return value for " + spyPointName +
            " which is not compatible with the return type of the agent deployed!");
      }
      return ret;
    } else {
      return SpyResult.absent();
    }
  }

  /**
   * Spies this point with no observation, expecting an Exception to be thrown.
   * Has no effect if {@link Bond#isActive()} is false.
   *
   * @see Bond#spyWithException(String)
   * @param spyPointName Name of the point being spied on.
   * @throws Exception If an Exception is available on the {@link SpyAgent}
   *         deployed for this point (if any).
   * @throws IllegalSpyAgentException If the SpyAgent available for this
   *         point is not a {@link bond.SpyAgent.SpyAgentWithCheckedException}.
   */
  public void spyWithException(String spyPointName) throws Exception {
    spyWithException(spyPointName, Exception.class);
  }

  /**
   * Spies this point with no observations, expecting a checked Exception of
   * type {@code expectedException} to be thrown. Has no effect if {@link Bond#isActive()}
   * is false.
   *
   * @see Bond#spyWithException(String, Class)
   * @param spyPointName Name of the point being spied on.
   * @param expectedException Type of Exception expected to be available on
   *                          any {@link SpyAgent} deployed for this point (if any).
   * @param <E> Same as expectedException.
   * @throws E If an Exception is available on the {@link SpyAgent} deployed for
   *         this point (if any).
   * @throws IllegalSpyAgentException If the type of Exception available on the
   *         {@link SpyAgent} for this point is not compatible with E, or if
   *         the agent is not a {@link bond.SpyAgent.SpyAgentWithCheckedException}.
   */
  public <E extends Exception> void spyWithException(String spyPointName,
                                                     Class<E> expectedException) throws E {
    if (!Bond.isActive()) {
      return;
    }
    try {
      SpyAgent.SpyAgentWithCheckedException agent =
          (SpyAgent.SpyAgentWithCheckedException) Bond.getAgent(spyPointName, _observationMap);
      processObservation(spyPointName);
      if (agent != null) {
        E e = (E) agent.getCheckedException(_observationMap);
        if (e != null && !expectedException.isAssignableFrom(e.getClass())) {
          throw new ClassCastException("jump to catch clause");
        }
        if (e != null) {
          throw e;
        }
      }
    } catch (ClassCastException e) {
      throw new IllegalSpyAgentException("Requested a return value / exception type for " + spyPointName +
                                             " which is not compatible with the agent deployed!");
    }
  }

  /**
   * Process the current observation, JSON-serializing it and adding it
   * to Bond's currently stored observations.
   *
   * @param spyPointName Name of this spy point
   */
  private void processObservation(String spyPointName) {
    if (spyPointName != null) {
      _observationMap.put("__spyPoint__", spyPointName);
    }

    Bond.addObservation(Bond.getSerializer().serialize(_observationMap));
  }

  /**
   * Check if the providedValue is compatible (that is, able to be returned into a variable of)
   * expectedType. If expectedType is {@code void}, this always returns true, useful for being able
   * to specify any return type to mark a method returning {@code void} as mocked out.
   *
   * @param providedValue The value to be returned
   * @param expectedType The expected type of that value
   * @return true iff providedValue can be stored into expectedType
   */
  private static boolean isTypeCompatible(Object providedValue, Class<?> expectedType) {
    if (expectedType == void.class) {
      return true;
    } else if (providedValue == null) {
      return Object.class.isAssignableFrom(expectedType);
    } else if (expectedType.isAssignableFrom(providedValue.getClass())) {
      return true;
    }
    Class<?>[] unboxedTypes = {byte.class, short.class, char.class, int.class, long.class, float.class, double.class, boolean.class};
    Class<?>[] boxedTypes = {Byte.class, Short.class, Character.class, Integer.class, Long.class, Float.class, Double.class, Boolean.class};
    for (int i = 0; i < unboxedTypes.length; i++) {
      if (providedValue.getClass() == boxedTypes[i] && expectedType == unboxedTypes[i]) {
        return true;
      }
    }
    return false;
  }
}
